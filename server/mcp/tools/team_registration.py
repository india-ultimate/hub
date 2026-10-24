from collections.abc import Callable
from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.db.models import Q

from server.core.models import Player, Team
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import ApiResponse, call_api, denied, refuse
from server.mcp.pay import pay_link
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, full_name, money, slug_problem
from server.receipts.money import rupees
from server.registration.models import RosterEntry
from server.series.models import SeriesRosterInvitation
from server.tournament.models import Event, Tournament
from server.tournament.utils import series_role
from server.utils import calculate_late_penalty, today

MAX_PLAYERS = 20
MAX_PAIRS = 20
HOLD_MINUTES = 20
NOT_ADMIN = "Only team admins can change this roster"
CHANGE_IT = "Already paid, or being paid: ask Hub in a help ticket ({}/tickets/new)."
PLAYER_IDS = {
    "type": "array",
    "items": {"type": "integer", "minimum": 1},
    "description": f"player_id values, at most {MAX_PLAYERS}",
}
WHAT = ("roster", "team_fee", "team_fee_partial")

ACTIONS: dict[str, tuple[str, str | None]] = {
    "ready": ("you", "pay_for_team"),
    "ready.free": ("you", "add_to_roster"),
    "action.invite": ("you", "add_to_roster"),
    "waiting.invite": ("you", "resend_roster_invites"),
    "waiting.invite_expired": ("you", "resend_roster_invites"),
    "waiting.declined": ("you", "remove_from_roster"),
    "progress.held": ("another admin", None),
}
STEP_TOOLS = {
    "register_series": "register_team",
    "register_free": "register_team",
    "pay_team": "pay_for_team",
    "pay_team_rest": "pay_for_team",
    "pay_team_partial": "pay_for_team",
}


def _ids_problem(ids: list[int]) -> ToolResult | None:
    if not ids or len(ids) > MAX_PLAYERS:
        return fail(f"player_ids: give between 1 and {MAX_PLAYERS} players")
    return None


def _base(event_slug: str, team_slug: str) -> str:
    return f"/api/registration/{event_slug}/team/{team_slug}"


def _admin_of(ctx: ToolContext, team_slug: str) -> Team | None:
    return ctx.user.admin_teams.filter(slug=team_slug).first()


def _load(ctx: ToolContext, event_slug: str, team_slug: str) -> tuple[Event, Team] | ToolResult:
    if problem := slug_problem(event_slug=event_slug, team_slug=team_slug):
        return problem
    event = Event.objects.filter(slug=event_slug, tournament__isnull=False).first()
    if event is None:
        return fail(f"No tournament with event_slug {event_slug}")
    team = Team.objects.filter(slug=team_slug).first()
    if team is None:
        return fail(f"No team with team_slug {team_slug}")
    return event, team


def _admin_load(
    ctx: ToolContext, event_slug: str, team_slug: str
) -> tuple[Event, Team] | ToolResult:
    loaded = _load(ctx, event_slug, team_slug)
    if isinstance(loaded, ToolResult):
        return loaded
    if _admin_of(ctx, team_slug) is None:
        return refuse(NOT_ADMIN)
    return loaded


def _name(player: Player) -> str:
    return full_name(player.user) or f"player {player.id}"


def _names(ids: list[int]) -> dict[int, str]:
    found = {p.id: _name(p) for p in Player.objects.filter(id__in=ids).select_related("user")}
    return {i: found.get(i, f"player {i}") for i in ids}


def _fee(event: Event, team: Team) -> dict[str, int]:
    """What the team fee costs this team today, as create_transaction charges it."""
    tournament = Tournament.objects.get(event=event)
    _, penalty = calculate_late_penalty(
        event.team_registration_end_date, event.team_late_penalty, event.team_late_penalty_end_date
    )
    full = event.team_fee
    if tournament.partial_teams.filter(pk=team.pk).exists():
        full = event.team_fee - event.partial_team_fee
    return {"team_fee": full + penalty, "team_fee_partial": event.partial_team_fee}


def _next(
    code: str, op: str | None, text: str, base: dict[str, str], player_id: int
) -> dict[str, Any]:
    by, tool_name = ACTIONS.get(code) or (
        ("you", {"invite": "add_to_roster", "resend_invite": "resend_roster_invites"}.get(op or ""))
        if op in ("invite", "resend_invite")
        else ("player", None)
    )
    row: dict[str, Any] = {"by": by, "tool": tool_name, "label": text}
    if tool_name == "pay_for_team":
        row["arguments"] = {**base, "what": "roster"}
    elif tool_name:
        row["arguments"] = {**base, "player_ids": [player_id]}
    return row


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    admin = data["viewer"] == "admin"
    steps = []
    for step in data["steps"]:
        callout = step["callout"] or {}
        row: dict[str, Any] = {
            "key": step["key"],
            "title": step["title"],
            "detail": step["detail"],
            "state": step["state"],
            "callout": callout.get("text"),
        }
        if admin:
            ops = [a["op"] for a in (callout.get("action"), callout.get("secondary_action")) if a]
            row["next_tools"] = sorted({STEP_TOOLS[o] for o in ops if o in STEP_TOOLS})
        steps.append(row)
    return {
        "team_id": data["team"]["id"],
        "team_slug": data["team"]["slug"],
        "event_slug": data["event"]["slug"],
        "all_set": data["all_set"],
        "viewer": data["viewer"],
        "steps": steps,
        "current_step": next((s["key"] for s in steps if s["state"] == "current"), None),
    }


def _player(entry: dict[str, Any], admin: bool, base: dict[str, str]) -> dict[str, Any]:
    state = entry["state"]
    row = {
        "player_id": entry["player"]["id"],
        "name": entry["player"]["name"],
        "state_code": state["code"],
        "kind": state["kind"],
        "text": state["text"],
    }
    if admin and state["kind"] != "done":
        action = state["action"] or {}
        row["next_action"] = _next(
            state["code"], action.get("op"), state["text"], base, entry["player"]["id"]
        )
    return row


def _registration(ctx: ToolContext, event_slug: str, team_slug: str) -> ToolResult:
    response = call_api(ctx, "GET", _base(event_slug, team_slug))
    if response.status == HTTPStatus.NOT_FOUND:
        return fail(
            f"No registration page for team_slug {team_slug} at event_slug {event_slug}",
            hint="The team must have a link to the tournament; list_team_events shows them.",
        )
    if not response.ok:
        return denied(response)
    data = response.data
    admin = data["viewer"] == "admin"
    checkout = data["checkout"]
    base = {"event_slug": event_slug, "team_slug": team_slug}
    out = {
        **_summary(data),
        "event": {
            "title": data["event"]["title"],
            "start_date": data["event"]["start_date"],
            "end_date": data["event"]["end_date"],
            "series_slug": None,
            "series": data["event"]["series"],
        },
        "meter": data["roster"]["meter"],
        "players": [_player(e, admin, base) for e in data["roster"]["entries"]],
    }
    event = Event.objects.select_related("series").get(slug=event_slug)
    out["event"]["series_slug"] = event.series.slug if event.series else None
    if not admin:
        out["note"] = "You can see this team's registration but only its admins can change it."
        return ok(cap(out, list_key="players", hint="Ask for fewer players or one at a time"))
    team = Team.objects.get(slug=team_slug)
    fees = _fee(event, team) if event.team_fee else {}
    out["team_fee"] = {
        "full": money(fees["team_fee"]) if fees else None,
        "partial": money(fees["team_fee_partial"]) if fees and fees["team_fee_partial"] else None,
    }
    out["checkout"] = {
        "ready_player_ids": checkout["ready_ids"],
        **money(checkout["amount"]),
        "per_player": money(checkout["per_player"] + checkout["penalty_per_player"]),
        "held_by_other_admin_player_ids": checkout["held_by_other_admin_ids"],
    }
    return ok(cap(out, list_key="players", hint="Ask about one player at a time"))


@tool(
    "get_team_registration",
    title="Where a team stands for an event",
    description=(
        "A team's registration for one tournament: the steps (series, team fee, roster) with "
        "their state, every player with why they are or are not ready and what to do next, "
        "the roster limits, the team fee, and what paying for the ready players would cost. "
        "Use it first when a team admin wants to get a team ready for an event."
    ),
    input_schema={
        "type": "object",
        "properties": {"event_slug": SLUG_SCHEMA, "team_slug": SLUG_SCHEMA},
        "required": ["event_slug", "team_slug"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
)
def get_team_registration(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    loaded = _load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    return _registration(ctx, args["event_slug"], args["team_slug"])


@tool(
    "list_team_events",
    title="Events my teams can register for",
    description=(
        "For the teams the user administers, the upcoming tournaments open for team "
        "registration or that the team is already in, each with whether it is all set and "
        "the step it is on. Pass team_slug for one team."
    ),
    input_schema={
        "type": "object",
        "properties": {"team_slug": SLUG_SCHEMA},
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
)
def list_team_events(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    team_slug = args.get("team_slug")
    if problem := slug_problem(team_slug=team_slug):
        return problem
    teams = ctx.user.admin_teams.order_by("name")
    if team_slug:
        teams = teams.filter(slug=team_slug)
        if not teams:
            return refuse(NOT_ADMIN)
    day = today()
    rows: list[dict[str, Any]] = []
    total = 0
    upcoming = list(
        Event.objects.filter(end_date__gte=day, tournament__isnull=False).order_by("start_date")
    )
    for team in teams:
        joined = set(
            Event.objects.filter(Q(tournament__teams=team) | Q(tournament__partial_teams=team))
            .order_by()
            .values_list("pk", flat=True)
        ) | set(RosterEntry.objects.filter(team=team).values_list("event_id", flat=True))
        for event in upcoming:
            last = max(
                filter(None, [event.team_late_penalty_end_date, event.team_registration_end_date])
            )
            if event.pk not in joined and not event.team_registration_start_date <= day <= last:
                continue
            total += 1
            if len(rows) >= MAX_PAIRS:
                continue
            if not event.slug or not team.slug:
                continue
            response = call_api(ctx, "GET", _base(event.slug, team.slug))
            if response.ok:
                rows.append(
                    {
                        "title": event.title,
                        "start_date": event.start_date.isoformat(),
                        "team_name": team.name,
                        **_summary(response.data),
                    }
                )
    out: dict[str, Any] = {"events": rows}
    if total > len(rows):
        out["truncated"] = {
            "shown": len(rows),
            "total": total,
            "hint": "Pass team_slug to see one team",
        }
    return ok(cap(out, list_key="events", hint="Pass team_slug to see one team"))


def _candidate(row: dict[str, Any], group: str) -> dict[str, Any]:
    hint = row["hint"] or {}
    return {
        "player_id": row["id"],
        "name": row["name"],
        "city": row["city"],
        "match_up": row["match_up"],
        "group": group,
        "on_list": row["on_list"],
        "would_email_invite": row["button"] == "invite",
        "state_code": hint.get("code"),
        "text": hint.get("text"),
    }


@tool(
    "find_team_candidates",
    title="Find players to add to a roster",
    description=(
        "Find players a team admin could add for an event, by name or by full email "
        "address (one lookup each, at most 20). Says whether adding someone also emails them "
        "a series invitation, and why they could not be added. With no text or emails, lists "
        "the series roster and past teammates. Results for emails give email_position (from 1) "
        "rather than the address."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "team_slug": SLUG_SCHEMA,
            "text": {"type": "string", "maxLength": 100},
            "emails": {
                "type": "array",
                "items": {"type": "string", "minLength": 3, "maxLength": 200},
                "description": f"Full email addresses, at most {MAX_PLAYERS}",
            },
        },
        "required": ["event_slug", "team_slug"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
)
def find_team_candidates(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    loaded = _admin_load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    emails = args.get("emails") or []
    if len(emails) > MAX_PLAYERS:
        return fail(f"emails: give at most {MAX_PLAYERS}")
    queries = emails or [args.get("text", "")]
    results = []
    for position, query in enumerate(queries, 1):
        response = call_api(
            ctx,
            "GET",
            f"{_base(args['event_slug'], args['team_slug'])}/candidates",
            query={"text": query.strip()},
        )
        if not response.ok:
            return denied(response)
        found = [_candidate(p, g["key"]) for g in response.data["groups"] for p in g["players"]]
        # An email is named by its position in emails: the address never goes back.
        asked = {"email_position": position} if emails else {"query": query}
        results.append({**asked, "found": bool(found), "candidates": found})
    return ok(cap({"results": results}, list_key="results", hint="Search fewer emails at a time"))


def _per_player(
    ctx: ToolContext,
    args: dict[str, Any],
    ids: list[int],
    call: Callable[[int], ApiResponse],
    done: str,
) -> ToolResult:
    names = _names(ids)
    results = [_outcome(i, names[i], call(i), done) for i in ids]
    failed = [r for r in results if not r["done"]]
    return ok({"done": not failed, "players": results, "failed": len(failed)})


def _outcome(player_id: int, name: str, response: ApiResponse, done: str) -> dict[str, Any]:
    row: dict[str, Any] = {"player_id": player_id, "name": name, "done": response.ok}
    if response.ok:
        state = response.data.get("state") if isinstance(response.data, dict) else None
        row["message"] = state["text"] if state else done
    elif response.status == HTTPStatus.CONFLICT:
        row["message"] = CHANGE_IT.format(settings.PUBLIC_URL)
    else:
        row["message"] = denied(response).data["message"]
    return row


def _list_names(ids: list[int], names: dict[int, str]) -> str:
    return ", ".join(names[i] for i in ids)


@tool(
    "add_to_roster",
    title="Add players to a team's roster",
    description=(
        "Add players to a team's roster for an event. On a series event, a player who is not "
        "on the series roster is emailed an invitation to join it. Paid events list them "
        "unpaid until pay_for_team. Asks the user first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "team_slug": SLUG_SCHEMA,
            "player_ids": PLAYER_IDS,
        },
        "required": ["event_slug", "team_slug", "player_ids"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    emails=True,
)
def add_to_roster(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := _ids_problem(args["player_ids"]):
        return problem
    loaded = _admin_load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    event, team = loaded
    ids = sorted(set(args["player_ids"]))
    players = {p.id: p for p in Player.objects.filter(id__in=ids).select_related("user")}
    if missing := [i for i in ids if i not in players]:
        return fail(f"No player with player_id {missing[0]}")
    already_invited = set(
        SeriesRosterInvitation.objects.filter(
            series=event.series,
            team=team,
            to_player_id__in=ids,
            status=SeriesRosterInvitation.Status.PENDING,
            expires_on__gte=today(),
        ).values_list("to_player_id", flat=True)
    )
    invited = [
        i
        for i in ids
        if event.series
        and players[i].user_id != ctx.user.pk
        and i not in already_invited
        and series_role(event, team, players[i]) is None
    ]
    listed = [i for i in ids if i not in invited]
    names = {i: _name(players[i]) for i in ids}
    roster = _base(args["event_slug"], args["team_slug"])
    parts = [f"Add {_list_names(ids, names)} to {team.name}'s roster for {event.title}."]
    if invited and event.series:
        parts.append(
            f"{_list_names(invited, names)} will get an email inviting them to join "
            f"{event.series.name}'s roster."
        )
    if listed:
        parts.append(f"{_list_names(listed, names)} will just be listed, with no email.")

    def run() -> ToolResult:
        return _per_player(
            ctx,
            args,
            ids,
            lambda i: call_api(ctx, "POST", f"{roster}/roster", body={"player_id": i}),
            "Added",
        )

    return confirm_then(
        ctx,
        message=" ".join(parts),
        binding={**args, "player_ids": ids, "invited_player_ids": invited},
        action=run,
        emails=len(invited),
    )


@tool(
    "remove_from_roster",
    title="Remove players from a team's roster",
    description=(
        "Take unpaid players off a team's roster for an event, and cancel their pending "
        "series invitation. Players who have paid cannot be removed here: send the user to "
        f"{settings.PUBLIC_URL}/tickets/new to ask Hub. Asks the user first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "team_slug": SLUG_SCHEMA,
            "player_ids": PLAYER_IDS,
        },
        "required": ["event_slug", "team_slug", "player_ids"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    destructive=True,
)
def remove_from_roster(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := _ids_problem(args["player_ids"]):
        return problem
    loaded = _admin_load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    event, team = loaded
    ids = sorted(set(args["player_ids"]))
    names = _names(ids)
    roster = _base(args["event_slug"], args["team_slug"])

    def run() -> ToolResult:
        return _per_player(
            ctx, args, ids, lambda i: call_api(ctx, "DELETE", f"{roster}/roster/{i}"), "Removed"
        )

    return confirm_then(
        ctx,
        message=(
            f"Remove {_list_names(ids, names)} from {team.name}'s roster for {event.title}. "
            "Nobody is emailed."
        ),
        binding={**args, "player_ids": ids},
        action=run,
        emails=len(ids),
    )


@tool(
    "resend_roster_invites",
    title="Resend series invitations",
    description=(
        "Email players on a team's roster a fresh invitation to join the series roster, "
        "replacing their earlier one. Asks the user first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "team_slug": SLUG_SCHEMA,
            "player_ids": PLAYER_IDS,
        },
        "required": ["event_slug", "team_slug", "player_ids"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    emails=True,
)
def resend_roster_invites(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := _ids_problem(args["player_ids"]):
        return problem
    loaded = _admin_load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    event, team = loaded
    ids = sorted(set(args["player_ids"]))
    names = _names(ids)
    roster = _base(args["event_slug"], args["team_slug"])

    def run() -> ToolResult:
        return _per_player(
            ctx,
            args,
            ids,
            lambda i: call_api(ctx, "POST", f"{roster}/roster/{i}/resend-invite"),
            "Invite sent again",
        )

    return confirm_then(
        ctx,
        message=(
            f"Email {_list_names(ids, names)} a new invitation to join "
            f"{team.name}'s roster for {event.title}. Their earlier invitation stops working."
        ),
        binding={**args, "player_ids": ids},
        action=run,
        emails=len(ids),
    )


def _order(response: ApiResponse, amount_paise: int, what: str) -> ToolResult:
    if response.status == HTTPStatus.CONFLICT:
        data = response.data if isinstance(response.data, dict) else {}
        if "new_amount" in data:
            return fail(
                f"The roster changed. It now costs {rupees(data['new_amount'])}, not "
                f"{rupees(data['old_amount'])}. No order was made.",
                removed=data["removed"],
                new_amount_paise=data["new_amount"],
                new_amount=rupees(data["new_amount"]),
                hint="Call get_team_registration and ask the user again.",
            )
        return fail(f"{response.message} No order was made.", hint="Ask the user again.")
    if not response.ok:
        return denied(response)
    order_id = response.data["order_id"]
    out = {
        "done": True,
        "order_id": order_id,
        "pay_url": pay_link(order_id),
        **money(amount_paise),
        "message": "Nothing is charged until the user pays on that page.",
    }
    if what == "roster":
        out[
            "message"
        ] += f" The players are held for {HOLD_MINUTES} minutes, so another admin cannot pay for them."
    return ok(out)


@tool(
    "pay_for_team",
    title="Get a pay link for a team",
    description=(
        "Make an order to pay for a team's ready players (what=roster), the team fee "
        "(team_fee) or the first part of it (team_fee_partial), and return a Hub pay_url for "
        "the user to open and pay. Nothing is charged until they pay. Quotes the price and "
        "asks the user first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "event_slug": SLUG_SCHEMA,
            "team_slug": SLUG_SCHEMA,
            "what": {"type": "string", "enum": list(WHAT)},
        },
        "required": ["event_slug", "team_slug", "what"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
)
def pay_for_team(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    loaded = _admin_load(ctx, args["event_slug"], args["team_slug"])
    if isinstance(loaded, ToolResult):
        return loaded
    event, team = loaded
    what = args["what"]
    status = call_api(ctx, "GET", _base(args["event_slug"], args["team_slug"]))
    if not status.ok:
        return denied(status)
    steps = {s["key"]: s for s in status.data["steps"]}
    if what == "roster":
        quote = status.data["checkout"]
        ids, amount = quote["ready_ids"], quote["amount"]
        if not event.player_fee:
            return fail("This event has no player fee.", hint="Use add_to_roster for free events.")
        if not ids:
            return fail(
                "No players are ready to pay for yet.",
                hint="Call get_team_registration to see what each player needs.",
            )
        names = _names(ids)
        message = (
            f"Make a pay link for {_list_names(ids, names)} on {team.name}'s roster for "
            f"{event.title}: {rupees(amount)} in all. Nothing is charged until you pay, and "
            f"they are held for {HOLD_MINUTES} minutes."
        )
        binding = {**args, "ready_player_ids": ids, "amount_paise": amount}

        def run_roster() -> ToolResult:
            body = {"expected_amount": amount, "expected_ids": ids}
            response = call_api(
                ctx, "POST", f"{_base(args['event_slug'], args['team_slug'])}/checkout", body=body
            )
            return _order(response, amount, what)

        return confirm_then(ctx, message=message, binding=binding, action=run_roster)

    if steps["team_fee"]["state"] == "done":
        return fail("The team fee is already paid.")
    if not event.team_fee:
        return fail("This event has no team fee.", hint="Use register_team for free events.")
    partial = what == "team_fee_partial"
    if partial and Tournament.objects.filter(event=event, partial_teams=team).exists():
        return fail(
            "The first part of the team fee is already paid.",
            hint='Pay the rest with what="team_fee".',
        )
    amount = _fee(event, team)[what]
    if not amount:
        return fail("This event has no partial team fee.")
    message = (
        f"Make a pay link for {team.name}'s {'first part of the ' if partial else ''}team fee "
        f"for {event.title}: {rupees(amount)}. Nothing is charged until you pay."
    )

    def run_fee() -> ToolResult:
        body = {
            "team_id": team.id,
            "event_id": event.id,
            "partial": partial,
            "expected_amount": amount,
        }
        return _order(call_api(ctx, "POST", "/api/transactions/razorpay", body=body), amount, what)

    return confirm_then(
        ctx,
        message=message,
        binding={**args, "team_id": team.id, "event_id": event.id, "amount_paise": amount},
        action=run_fee,
    )


@tool(
    "register_team",
    title="Register a team for a series or a free event",
    description=(
        "Register one of the user's teams for a series (series_slug) or for a free "
        "tournament (event_slug). A tournament with a team fee is paid with pay_for_team "
        "instead. Asks the user first."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "team_slug": SLUG_SCHEMA,
            "series_slug": SLUG_SCHEMA,
            "event_slug": SLUG_SCHEMA,
        },
        "required": ["team_slug"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
)
def register_team(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    series_slug, event_slug = args.get("series_slug"), args.get("event_slug")
    if (series_slug is None) == (event_slug is None):
        return fail("Give exactly one of series_slug or event_slug")
    if problem := slug_problem(
        team_slug=args["team_slug"], series_slug=series_slug, event_slug=event_slug
    ):
        return problem
    team = Team.objects.filter(slug=args["team_slug"]).first()
    if team is None:
        return fail(f"No team with team_slug {args['team_slug']}")
    if not ctx.user.admin_teams.filter(pk=team.pk).exists():
        return refuse("Only team admins can register a team")
    if series_slug is not None:
        message = f"Register {team.name} for the series {series_slug}. It costs nothing."

        def run() -> ToolResult:
            response = call_api(
                ctx,
                "POST",
                f"/api/series/{series_slug}/register-team",
                body={"team_slug": team.slug},
            )
            if not response.ok:
                return denied(response)
            return ok({"done": True, "message": f"{team.name} is registered for the series."})

    else:
        tournament = (
            Tournament.objects.select_related("event").filter(event__slug=event_slug).first()
        )
        if tournament is None:
            return fail(f"No tournament with event_slug {event_slug}")
        event = tournament.event
        if event.team_fee:
            return fail(
                f"{event.title} has a team fee of {rupees(event.team_fee)}.",
                hint="Use pay_for_team with what=team_fee.",
            )
        message = f"Register {team.name} for {event.title}. It costs nothing."

        def run() -> ToolResult:
            response = call_api(
                ctx,
                "PUT",
                f"/api/tournament/{tournament.id}/register-team",
                body={"team_id": team.id},
            )
            if not response.ok:
                return denied(response)
            return ok({"done": True, "message": f"{team.name} is registered for {event.title}."})

    return confirm_then(ctx, message=message, binding=args, action=run)
