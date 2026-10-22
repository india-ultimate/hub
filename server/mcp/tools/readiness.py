import datetime
from typing import Any

from django.conf import settings
from django.db.models import Q

from server.core.models import Player
from server.mcp.dispatch import call_api
from server.mcp.pay import pay_link, unpaid_membership
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, slug_problem
from server.mcp.tools.profile import player_ids
from server.registration.models import RosterEntry
from server.series.models import Series, SeriesRosterInvitation
from server.series.utils import invitations_for
from server.subscription import eligibility
from server.tournament.models import Event, Registration
from server.utils import today

FIX_PATHS = {
    "subscription": "subscription",
    "waiver": "waiver",
    "coc": "code-of-conduct",
    "accreditation": "accreditation",
    "commentary_info": "commentary-info",
    "college_id": "college-id",
}


def _college_id_active(college_id: dict[str, Any] | None, on: datetime.date) -> bool:
    return (
        college_id is not None
        and not college_id["images_removed_at"]
        and datetime.date.fromisoformat(college_id["expiry"]) >= on
    )


def checklist(player: dict[str, Any], on: datetime.date) -> dict[str, bool]:
    subscription = player.get("subscription") or {}
    accreditation = player.get("accreditation") or {}
    student = player.get("occupation") == "College-Student"
    return {
        "profile": bool(player.get("id")),
        "subscription": bool(subscription.get("is_active")),
        "waiver": bool(subscription.get("waiver_valid")),
        "coc": bool(subscription.get("coc_agreed")),
        "accreditation": bool(accreditation.get("is_valid")),
        "commentary_info": bool(player.get("commentary_info")),
        "college_id": _college_id_active(player.get("college_id"), on) if student else True,
    }


NOT_REQUIRED = ("college_id", "commentary_info")


def _step(
    item: str,
    why: str,
    tool_name: str | None,
    arguments: dict[str, Any],
    required: bool = True,
) -> dict[str, Any]:
    return {
        "item": item,
        "why": why,
        "tool": tool_name,
        "arguments": arguments,
        "required_to_play": required,
    }


def next_steps(
    player_id: int, status: dict[str, bool], unpaid_order: str | None = None
) -> list[dict[str, Any]]:
    """What to do, in the order Hub needs it: signing waits for a membership."""
    steps = {
        "subscription": _step(
            "subscription",
            "A membership is needed to play and before the waiver and code of conduct can be "
            "signed. Show the options, then buy_membership for the one they pick.",
            "get_membership_options",
            {"player_ids": [player_id]},
        ),
        "waiver": _step(
            "waiver",
            "Sign this season's waiver. It needs the membership first.",
            "sign_document",
            {"player_id": player_id, "document": "waiver"},
        ),
        "coc": _step(
            "coc",
            "Agree to this season's code of conduct. It needs the membership first.",
            "sign_document",
            {"player_id": player_id, "document": "coc"},
        ),
        "accreditation": _step(
            "accreditation",
            "The WFDF Academy accreditation certificate (PDF) is required to play. Create an "
            "upload link and have the user upload the certificate there.",
            "create_upload_link",
            {"kind": "accreditation", "player_id": player_id},
        ),
        "college_id": _step(
            "college_id",
            "A college student needs a current college ID on file. Create an upload link for "
            "the card's front and back.",
            "create_upload_link",
            {"kind": "college_id", "player_id": player_id},
            required=False,
        ),
        "commentary_info": _step(
            "commentary_info",
            "Hub asks for commentary details: jersey number, how they found ultimate, what "
            "they like, favourite role and experience, interests and a fun fact. Ask the user, "
            "then call update_profile with changes.commentary_info.",
            "update_profile",
            {"player_id": player_id},
            required=False,
        ),
    }
    if unpaid_order:
        steps["subscription"] = {
            **_step(
                "subscription",
                "A membership order for them is waiting to be paid. Give the user its pay_url "
                "to finish paying; list_my_payments (kind unpaid) shows it again. Do not buy a "
                "second one.",
                "list_my_payments",
                {"kind": "unpaid"},
            ),
            "pay_url": pay_link(unpaid_order),
        }
    return [steps[item] for item in steps if not status[item]]


def _roster(
    ctx: ToolContext, event: Event, player_id: int
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Where the player stands on a team for the event, and the step that follows."""
    registration = (
        Registration.objects.filter(event=event, player_id=player_id).select_related("team").first()
    )
    if registration:
        team = registration.team
        status = "rostered" if registration.is_playing else "rostered_not_playing"
        return {"status": status, "team_name": team.name, "team_slug": team.slug}, None
    entry = (
        RosterEntry.objects.filter(event=event, player_id=player_id).select_related("team").first()
    )
    if entry:
        team = entry.team
        return (
            {"status": "on_roster_unpaid", "team_name": team.name, "team_slug": team.slug},
            _step(
                "roster",
                f"{team.name} has listed them but the team fee is not paid yet. Their team "
                "admin pays it to confirm the spot.",
                None,
                {},
            ),
        )
    invitation = (
        invitations_for(ctx.user)
        .filter(
            series_id=event.series_id,
            to_player_id=player_id,
            status=SeriesRosterInvitation.Status.PENDING,
        )
        .select_related("team")
        .first()
        if event.series_id
        else None
    )
    if invitation:
        team = invitation.team
        return (
            {
                "status": "invited",
                "invitation_id": invitation.pk,
                "team_name": team.name,
                "team_slug": team.slug,
            },
            _step(
                "roster",
                f"{team.name} invited them to its roster. Ask whether to accept, then "
                "answer_series_invitation.",
                "answer_series_invitation",
                {"invitation_id": invitation.pk, "answer": "accept"},
            ),
        )
    return (
        {"status": "not_on_a_team"},
        _step(
            "roster",
            "They are not on a team for this event. Ask their team admin to add them.",
            None,
            {},
        ),
    )


def _can_play(player_id: int, target: Event | Series) -> dict[str, Any]:
    error = eligibility.check(Player.objects.get(id=player_id), target, is_playing=True)
    return {"ok": error is None, "reason": error["message"] if error else None}


@tool(
    "get_readiness",
    title="What I still need to play",
    description=(
        "What the signed-in user and their wards still need before they can play (document status alone is get_documents), the same "
        "checklist as the Hub dashboard, with a link to fix each missing item. Pass player_id "
        "for one person. Pass event_slug or series_slug to also see whether they can play there; "
        "event_slug also shows whether they are on a team's roster. next_steps lists what to do "
        "next, in order, each naming the tool to call and its arguments: walk the user through "
        "them one at a time. Steps with required_to_play=false never block play."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "player_id": {"type": "integer"},
            "event_slug": SLUG_SCHEMA,
            "series_slug": SLUG_SCHEMA,
        },
        "additionalProperties": False,
    },
)
def get_readiness(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(
        event_slug=args.get("event_slug"), series_slug=args.get("series_slug")
    ):
        return problem
    targets: dict[str, Event | Series] = {}
    event: Event | None = None
    if "event_slug" in args:
        event = Event.objects.filter(slug=args["event_slug"]).first()
        if event is None:
            return fail(f"No tournament with event_slug {args['event_slug']}")
        targets["can_play"] = event
    if "series_slug" in args:
        series = Series.objects.filter(slug=args["series_slug"]).first()
        if series is None:
            return fail(f"No series with series_slug {args['series_slug']}")
        targets["can_play_series"] = series

    ids = player_ids(ctx, args)
    if isinstance(ids, ToolResult):
        return ids
    if not ids:
        return ok(
            {
                "players": [],
                "next_step": {
                    "message": "Create your player profile to start playing.",
                    "url": f"{settings.PUBLIC_URL}/registration/me",
                },
                "next_steps": [
                    _step(
                        "profile",
                        "No player profile yet. Ask for name, phone, date of birth, gender, "
                        "match-up, city (and state), then create_profile. For a child under 18, "
                        "use for=ward.",
                        "create_profile",
                        {"for": "me"},
                    )
                ],
            }
        )
    mine = (
        set(
            Player.objects.filter(Q(user=ctx.user) | Q(guardianship__user=ctx.user)).values_list(
                "id", flat=True
            )
        )
        if event is not None
        else set()
    )

    players = []
    for player_id in ids:
        response = call_api(ctx, "GET", f"/api/players/{player_id}")
        if not response.ok:
            return fail(response.message)
        if "accreditation" not in response.data:
            subscription = response.data.get("subscription") or {}
            players.append(
                {
                    "player_id": player_id,
                    "full_name": response.data["full_name"],
                    "membership_active": bool(subscription.get("is_active")),
                    "note": "You can see only membership status for this player.",
                }
            )
            continue
        status = checklist(response.data, today())
        missing = [
            {
                "item": item,
                "required_to_play": item not in NOT_REQUIRED,
                "fix_url": f"{settings.PUBLIC_URL}/{path}/{player_id}",
            }
            for item, path in FIX_PATHS.items()
            if not status[item]
        ]
        entry: dict[str, Any] = {
            "player_id": player_id,
            "full_name": response.data["full_name"],
            "ready": not any(m["required_to_play"] for m in missing),
            "missing": missing,
        }
        entry["next_steps"] = next_steps(
            player_id,
            status,
            unpaid_membership(ctx.user, player_id) if not status["subscription"] else None,
        )
        for key, target in targets.items():
            entry[key] = _can_play(player_id, target)
        if event is not None and player_id in mine:
            entry["roster"], step = _roster(ctx, event, player_id)
            if step:
                entry["next_steps"].append(step)
        entry["next_steps"].sort(key=lambda step: not step["required_to_play"])
        players.append(entry)
    return ok({"players": players})
