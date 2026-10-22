import json
from typing import Any

from server.core.models import Player, StatesUTs, Team, UCPerson
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import ApiResponse, call_api, denied, refuse
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, full_name, slug_problem
from server.series.models import Role, SeriesRosterInvitation
from server.tournament.models import Match
from server.tournament.utils import user_tournament_teams
from server.utils import today

ROLES = [code for code, _ in Role.choices]
ROLE_SCHEMA = {"type": "string", "enum": ROLES}
SERIES_ARGS = {"series_slug": SLUG_SCHEMA, "team_slug": SLUG_SCHEMA}
MAX_BATCH = 20
MAX_SPIRIT_SCORE = 4
NOMINEE_KEYS = ["mvp_player_id", "msp_player_id", "mvp_uc_person_id", "msp_uc_person_id"]
SPIRIT_FIELDS = ["rules", "fouls", "fair", "positive", "communication"]
NOT_A_SCORER = (
    "only a captain, spirit captain, coach, assistant coach or manager on "
    "the team's roster for this event can submit its scores. Being a team admin is not "
    "enough. Ask the captain, or have the roster list you with one of those roles."
)


def _slugs_problem(args: dict[str, Any]) -> ToolResult | None:
    return slug_problem(series_slug=args.get("series_slug"), team_slug=args.get("team_slug"))


def _series_path(args: dict[str, Any], tail: str) -> str:
    return f"/api/series/{args['series_slug']}/team/{args['team_slug']}/{tail}"


def _player_name(player_id: int) -> str:
    player = Player.objects.select_related("user").filter(pk=player_id).first()
    name = full_name(player.user) if player else ""
    return name or f"player {player_id}"


def _roster(ctx: ToolContext, args: dict[str, Any]) -> ApiResponse:
    return call_api(ctx, "GET", _series_path(args, "roster"))


@tool(
    "get_series_roster",
    title="Series roster",
    description=(
        "A team's roster for a series: each member's registration_id, player_id, name and "
        "role (DFLT player, CAP captain, SCAP spirit captain, COACH, ACOACH, MNGR). "
        "Team admins also get pending_invitations with invitation_id, and expired set when "
        "the invitation has lapsed."
    ),
    input_schema={
        "type": "object",
        "properties": SERIES_ARGS,
        "required": ["series_slug", "team_slug"],
        "additionalProperties": False,
    },
)
def get_series_roster(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := _slugs_problem(args):
        return problem
    response = _roster(ctx, args)
    if not response.ok:
        return fail(response.message)
    members = [
        {
            "registration_id": row["id"],
            "player_id": row["player"]["id"],
            "full_name": row["player"]["full_name"],
            "role": row["role"],
        }
        for row in response.data
    ]
    sent = call_api(ctx, "GET", _series_path(args, "invitations-sent"))
    pending = [
        {
            "invitation_id": row["id"],
            "player_id": row["to_player"]["id"],
            "full_name": row["to_player"]["full_name"],
            "role": row["role"],
            "expires_on": row["expires_on"],
            "expired": row["expires_on"] < str(today()),
        }
        for row in (sent.data if sent.ok else [])
        if row["status"] == "Pending"
    ]
    data = {
        **args,
        "members": members,
        "pending_invitations": pending,
        "can_manage": sent.status not in (401, 403),
    }
    return ok(cap(data, list_key="members", hint="Ask about one player at a time"))


@tool(
    "invite_to_series_roster",
    title="Invite players to a series roster",
    description=(
        "Invite players (by player_id, from search) to a team's series roster. Each player "
        "is emailed an invitation to accept or decline. Team admins only. Role defaults "
        "to DFLT (player)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            **SERIES_ARGS,
            "invites": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "player_id": {"type": "integer", "minimum": 1},
                        "role": ROLE_SCHEMA,
                    },
                    "required": ["player_id"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["series_slug", "team_slug", "invites"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    emails=True,
)
def invite_to_series_roster(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    invites = args["invites"]
    if problem := _slugs_problem(args):
        return problem
    if not 0 < len(invites) <= MAX_BATCH:
        return fail(f"Give between 1 and {MAX_BATCH} invites")
    names = ", ".join(_player_name(i["player_id"]) for i in invites)

    def action() -> ToolResult:
        results = []
        for invite in invites:
            body = {"to_player_id": invite["player_id"], "role": invite.get("role")}
            response = call_api(ctx, "POST", _series_path(args, "invitation"), body=body)
            results.append(
                {"player_id": invite["player_id"], "outcome": "invited"}
                if response.ok
                else {
                    "player_id": invite["player_id"],
                    "outcome": "failed",
                    "message": denied(response).data["message"],
                }
            )
        if all(r["outcome"] == "failed" for r in results):
            return fail(results[0]["message"], results=results)
        return ok({"results": results})

    return confirm_then(
        ctx,
        message=f"Email a series roster invitation to {names} for team {args['team_slug']}?",
        binding=args,
        action=action,
        emails=len(invites),
    )


@tool(
    "revoke_series_invitations",
    title="Revoke series roster invitations",
    description=(
        "Cancel pending series roster invitations by invitation_id (from get_series_roster). "
        "Nobody is emailed. Team admins only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "invitation_ids": {"type": "array", "items": {"type": "integer", "minimum": 1}}
        },
        "required": ["invitation_ids"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    destructive=True,
)
def revoke_series_invitations(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    ids = args["invitation_ids"]
    if not 0 < len(ids) <= MAX_BATCH:
        return fail(f"Give between 1 and {MAX_BATCH} invitation_ids")

    # Only invitations of the caller's own teams, as the revoke route allows, so the
    # question names nobody else's players.
    invited = SeriesRosterInvitation.objects.filter(
        pk__in=ids, team__admins=ctx.user
    ).select_related("to_player__user", "team")
    if missing := sorted(set(ids) - {i.pk for i in invited}):
        return fail(
            f"No pending invitation of your teams with invitation_id {missing}.",
            hint="get_series_roster lists your team's invitations.",
        )
    names = ", ".join(
        (full_name(i.to_player.user) or "a player") + f" ({i.team.name})" for i in invited
    )

    def action() -> ToolResult:
        results = []
        for invitation_id in ids:
            response = call_api(ctx, "DELETE", f"/api/series/invitation/{invitation_id}")
            if not response.ok:
                return denied(response)
            results.append({"invitation_id": invitation_id, "outcome": "revoked"})
        return ok({"results": results})

    return confirm_then(
        ctx,
        message=f"Revoke the series roster invitation for {names}? It can no longer be accepted.",
        binding=args,
        action=action,
    )


@tool(
    "set_series_roles",
    title="Change series roster roles",
    description=(
        "Change roles on a team's series roster, by player_id. Roles: DFLT player, CAP captain, "
        "SCAP spirit captain, COACH, ACOACH, MNGR. Changes the series role only. Team admins only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            **SERIES_ARGS,
            "changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "player_id": {"type": "integer", "minimum": 1},
                        "role": ROLE_SCHEMA,
                    },
                    "required": ["player_id", "role"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["series_slug", "team_slug", "changes"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    destructive=True,
)
def set_series_roles(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    changes = args["changes"]
    if problem := _slugs_problem(args):
        return problem
    if not 0 < len(changes) <= MAX_BATCH:
        return fail(f"Give between 1 and {MAX_BATCH} changes")
    roster = _roster(ctx, args)
    if not roster.ok:
        return fail(roster.message)
    registrations = {r["player"]["id"]: r["id"] for r in roster.data}
    for change in changes:
        if change["player_id"] not in registrations:
            return fail(
                f"player_id {change['player_id']} is not on the series roster",
                hint="Invite them first, or check get_series_roster",
            )

    def action() -> ToolResult:
        for change in changes:
            path = _series_path(args, f"roster/{registrations[change['player_id']]}/role")
            response = call_api(ctx, "PUT", path, body={"role": change["role"]})
            if not response.ok:
                return denied(response)
        return ok({"changed": [c["player_id"] for c in changes]})

    lines = ", ".join(f"{_player_name(c['player_id'])} to {c['role']}" for c in changes)
    return confirm_then(
        ctx,
        message=f"Change series roles on team {args['team_slug']}: {lines}?",
        binding=args,
        action=action,
    )


@tool(
    "add_myself_to_series_roster",
    title="Add myself to a series roster",
    description=(
        "Put yourself on a team's series roster as a player. You must be an admin of the team "
        "and meet the series' eligibility rules; Hub says why if not."
    ),
    input_schema={
        "type": "object",
        "properties": SERIES_ARGS,
        "required": ["series_slug", "team_slug"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
)
def add_myself_to_series_roster(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := _slugs_problem(args):
        return problem

    def action() -> ToolResult:
        response = call_api(ctx, "POST", _series_path(args, "roster/add-self"))
        if not response.ok:
            return denied(response)
        return ok({**args, "registration_id": response.data["id"]})

    return confirm_then(
        ctx,
        message=f"Add you to team {args['team_slug']}'s roster for series {args['series_slug']}?",
        binding=args,
        action=action,
    )


def _admin_user_ids(player_ids: list[int]) -> list[int] | None:
    found = dict(Player.objects.filter(pk__in=player_ids).values_list("pk", "user_id"))
    return None if len(found) != len(set(player_ids)) else list(found.values())


@tool(
    "update_team",
    title="Update team details",
    description=(
        "Change a team's name, category, state_ut, city, or its admins (add or remove by "
        "player_id). Renaming changes the team's Hub link (team_slug), so saved links break; "
        "the new team_slug is returned. Team admins only. To change the logo, use "
        "create_upload_link(kind=team_logo); to create a new team, "
        "create_upload_link(kind=new_team)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "team_slug": SLUG_SCHEMA,
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "category": {"type": "string", "enum": [c for c, _ in Team.CategoryTypes.choices]},
            "state_ut": {"type": "string", "enum": list(StatesUTs.values)},
            "city": {"type": "string", "minLength": 1, "maxLength": 30},
            "add_admin_player_ids": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "remove_admin_player_ids": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
            },
        },
        "required": ["team_slug"],
        "additionalProperties": False,
    },
    audience=Audience.TEAM_ADMIN,
    writes=True,
    destructive=True,
)
def update_team(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(team_slug=args["team_slug"]):
        return problem
    current = call_api(ctx, "GET", f"/api/team/{args['team_slug']}")
    if not current.ok:
        return fail(current.message)
    team = current.data
    admins = {a["id"] for a in team["admins"]}
    if ctx.user.pk not in admins:
        return refuse("only an admin of the team can change it")

    details: dict[str, Any] = {k: args[k] for k in ("category", "state_ut", "city") if k in args}
    name = args.get("name", "").strip()
    if "name" in args and not name:
        return fail("name can't be blank")
    adds, removes = args.get("add_admin_player_ids", []), args.get("remove_admin_player_ids", [])
    new_admins = admins
    if adds or removes:
        add_users, remove_users = _admin_user_ids(adds), _admin_user_ids(removes)
        if add_users is None or remove_users is None:
            return fail("Some of those player_ids don't exist")
        new_admins = (admins | set(add_users)) - set(remove_users)
        if ctx.user.pk not in new_admins:
            return fail("You can't remove yourself as an admin")
        if new_admins != admins:
            details["admin_ids"] = sorted(new_admins)
    if name == team["name"]:
        name = ""
    if not details and not name:
        return fail("Nothing to change")

    def action() -> ToolResult:
        slug = team["slug"]
        if details:
            response = call_api(
                ctx,
                "POST",
                "/api/teams/edit",
                body={"team_details": json.dumps({"id": str(team["id"]), **details})},
                files={},
            )
            if not response.ok:
                return denied(response)
        if name:
            response = call_api(
                ctx, "PUT", "/api/teams/edit-name", body={"id": str(team["id"]), "name": name}
            )
            if not response.ok:
                return denied(response)
            slug = response.data["slug"]
        fresh = call_api(ctx, "GET", f"/api/team/{slug}")
        return ok(_team_summary(fresh.data))

    notes = [f"{k}: {v}" for k, v in details.items() if k != "admin_ids"]
    if name:
        notes.append(f"name: {name} (this changes the team's Hub link, so saved links break)")
    if "admin_ids" in details:
        notes.append(
            "admins: add "
            + (", ".join(_player_name(i) for i in adds) or "nobody")
            + "; remove "
            + (", ".join(_player_name(i) for i in removes) or "nobody")
        )
    return confirm_then(
        ctx,
        message=f"Update team {team['name']}? " + "; ".join(notes),
        binding=args,
        action=action,
    )


def _team_summary(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": team["id"],
        "team_slug": team["slug"],
        "name": team["name"],
        "category": team["category"],
        "state_ut": team["state_ut"],
        "city": team["city"],
        "admins": [{"user_id": a["id"], "full_name": a["full_name"]} for a in team["admins"]],
    }


def _load_match(match_id: int) -> Match | None:
    return (
        Match.objects.select_related("tournament__event", "team_1", "team_2")
        .filter(pk=match_id)
        .first()
    )


@tool(
    "list_match_rosters",
    title="Match rosters",
    description=(
        'Find match_id with get_tournament(event_slug, view="schedule", team_slug). '
        "The rostered players of both teams in a match, as player_id and name (for tournaments on Ultimate Central "
        "registrations, uc_person_id instead), for choosing the MVP and MSP in "
        "submit_spirit_score: pass player_id as mvp_player_id/msp_player_id, or uc_person_id "
        "as mvp_uc_person_id/msp_uc_person_id. Nominees must be on the opponent's roster."
    ),
    input_schema={
        "type": "object",
        "properties": {"match_id": {"type": "integer", "minimum": 1}},
        "required": ["match_id"],
        "additionalProperties": False,
    },
)
def list_match_rosters(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    match = _load_match(args["match_id"])
    if match is None or match.team_1 is None or match.team_2 is None:
        return fail("That match does not exist or does not have both teams yet")
    event = match.tournament.event.slug
    version = "v1" if match.tournament.use_uc_registrations else "v2"
    uc = version == "v1"
    id_key = "uc_person_id" if uc else "player_id"
    out: dict[str, Any] = {"match_id": match.pk, "id_kind": id_key}
    for key, team in (("team_1", match.team_1), ("team_2", match.team_2)):
        response = call_api(
            ctx, "GET", f"/api/{version}/tournament/{event}/team/{team.slug}/roster"
        )
        if not response.ok:
            return fail(response.message)
        rows = (
            [r["person"] for r in response.data]
            if version == "v1"
            else [r["player"] for r in response.data]
        )
        out[key] = {
            "team_id": team.pk,
            "name": team.name,
            "players": [
                {
                    id_key: p["id"],
                    "full_name": full_name(p) if version == "v1" else p["full_name"],
                }
                for p in rows
            ],
        }
    return ok(out)


def _scorer_teams(ctx: ToolContext, match: Match) -> set[int]:
    return user_tournament_teams(match.tournament, ctx.user)[1]


@tool(
    "submit_match_score",
    title="Submit a match score",
    description=(
        'Find match_id with get_tournament(event_slug, view="schedule", team_slug). '
        "Submit your team's view of a match's final score. Scores are in match order "
        "(team_1_score for team_1, as get_match shows), not mine and theirs. The match is "
        "final once both teams submit the same score. Needs a captain, coach or manager role "
        "on the team's event roster."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "match_id": {"type": "integer", "minimum": 1},
            "team_1_score": {"type": "integer", "minimum": 0},
            "team_2_score": {"type": "integer", "minimum": 0},
        },
        "required": ["match_id", "team_1_score", "team_2_score"],
        "additionalProperties": False,
    },
    audience=Audience.CAPTAIN,
    writes=True,
    destructive=True,
)
def submit_match_score(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    match = _load_match(args["match_id"])
    if match is None:
        return fail(f"No match with match_id {args['match_id']}")
    if match.team_1 is None or match.team_2 is None:
        return fail("This match does not have both teams yet")
    first, second = match.team_1, match.team_2
    if match.status in (Match.Status.COMPLETED, Match.Status.YET_TO_FIX):
        return fail("A score can't be submitted for this match in its current status")
    if not {first.pk, second.pk} & _scorer_teams(ctx, match):
        return refuse(NOT_A_SCORER)
    one, two = args["team_1_score"], args["team_2_score"]

    def action() -> ToolResult:
        response = call_api(
            ctx,
            "POST",
            f"/api/match/{match.pk}/submit-score",
            body={"team_1_score": one, "team_2_score": two},
        )
        if not response.ok:
            return denied(response)
        data = response.data
        mine, other = data["suggested_score_team_1"], data["suggested_score_team_2"]
        if data["status"] == Match.Status.COMPLETED:
            outcome = "final"
        elif mine and other:
            outcome = "disagree"
        else:
            outcome = "waiting"
        words = {
            "final": "Both teams agree: the match is final.",
            "disagree": "The other team submitted a different score. Talk to them and resubmit.",
            "waiting": "Saved. Waiting for the other team to submit their score.",
        }
        return ok(
            {
                "match_id": match.pk,
                "outcome": outcome,
                "message": words[outcome],
                "team_1": {"team_id": first.pk, "name": first.name, "score": one},
                "team_2": {"team_id": second.pk, "name": second.name, "score": two},
            }
        )

    return confirm_then(
        ctx,
        message=(
            f"Submit {first.name} {one} - {two} {second.name}? "
            "If the other team's score agrees, the match is final."
        ),
        binding=args,
        action=action,
    )


def _spirit_block(include_nominees: bool) -> dict[str, Any]:
    score = {"type": "integer", "minimum": 0, "maximum": 4}
    properties: dict[str, Any] = dict.fromkeys(SPIRIT_FIELDS, score)
    properties["comments"] = {"type": "string", "maxLength": 500}
    if include_nominees:
        for key in NOMINEE_KEYS:
            properties[key] = {"type": "integer", "minimum": 1}
    return {
        "type": "object",
        "properties": properties,
        "required": SPIRIT_FIELDS,
        "additionalProperties": False,
    }


def _nominee_name(match: Match, nominee_id: int | None) -> str:
    if nominee_id is None:
        return "nobody"
    if match.tournament.use_uc_registrations:
        person = UCPerson.objects.filter(pk=nominee_id).first()
        return full_name(person) if person else str(nominee_id)
    return _player_name(nominee_id)


def _nominee(block: dict[str, Any], key: str) -> int | None:
    return block.get(f"{key}_player_id") or block.get(f"{key}_uc_person_id")


def _spirit_body(block: dict[str, Any]) -> dict[str, Any]:
    body = {k: block[k] for k in SPIRIT_FIELDS}
    body["comments"] = block.get("comments")
    for key in ("mvp", "msp"):
        value = _nominee(block, key)
        body[f"{key}_id"] = None if value is None else str(value)
    return body


@tool(
    "submit_spirit_score",
    title="Submit spirit scores",
    description=(
        'Find match_id with get_tournament(event_slug, view="schedule", team_slug). '
        "Submit your team's spirit scores for a match: opponent (the scores you give them, "
        "each 0 to 4, plus the MVP and MSP from list_match_rosters, who must be on their "
        "roster) and self (your own assessment). Nominate by mvp_player_id/msp_player_id, or "
        "by mvp_uc_person_id/msp_uc_person_id when list_match_rosters gives uc_person_id. Submit the match score first. Replaces any "
        "earlier spirit submission by your team. Needs a captain, coach or manager role "
        "on your team's event roster."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "match_id": {"type": "integer", "minimum": 1},
            "team_id": {"type": "integer", "minimum": 1},
            "opponent": _spirit_block(True),
            "self": _spirit_block(False),
        },
        "required": ["match_id", "team_id", "opponent", "self"],
        "additionalProperties": False,
    },
    audience=Audience.CAPTAIN,
    writes=True,
    destructive=True,
)
def submit_spirit_score(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    match = _load_match(args["match_id"])
    if match is None:
        return fail(f"No match with match_id {args['match_id']}")
    if match.team_1 is None or match.team_2 is None:
        return fail("This match does not have both teams yet")
    teams = {match.team_1.pk: match.team_2, match.team_2.pk: match.team_1}
    if args["team_id"] not in teams:
        return fail("team_id is not one of the two teams in this match")
    if args["team_id"] not in _scorer_teams(ctx, match):
        return refuse(NOT_A_SCORER)
    for side in ("opponent", "self"):
        for field in SPIRIT_FIELDS:
            if args[side][field] > MAX_SPIRIT_SCORE:
                return fail(f"{side}.{field}: must be at most {MAX_SPIRIT_SCORE}")
    opponent = args["opponent"]

    def action() -> ToolResult:
        body = {
            "team_id": args["team_id"],
            "opponent": _spirit_body(opponent),
            "self": _spirit_body(args["self"]),
        }
        response = call_api(ctx, "POST", f"/api/match/{match.pk}/submit-spirit-score", body=body)
        if not response.ok:
            return denied(response)
        return ok({"match_id": match.pk, "team_id": args["team_id"], "saved": True})

    total = sum(opponent[k] for k in SPIRIT_FIELDS)
    return confirm_then(
        ctx,
        message=(
            f"Submit spirit scores for {teams[args['team_id']].name}: total {total} out of 20, "
            f"MVP {_nominee_name(match, _nominee(opponent, 'mvp'))}, "
            f"MSP {_nominee_name(match, _nominee(opponent, 'msp'))}. "
            "This replaces any spirit scores your team already submitted for this match."
        ),
        binding=args,
        action=action,
    )
