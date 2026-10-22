from typing import Any

from django.conf import settings
from django.utils.timezone import now

from server.core.models import Team
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import refuse
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool, validate
from server.mcp.shape import SLUG_SCHEMA, cap
from server.tournament.models import Match, Registration, Tournament
from server.tournament.utils import can_manage_tournament, is_submitted_scores_equal
from server.tournament_agent.catalog import default_model_id
from server.tournament_agent.domain.phase import phase_for
from server.tournament_agent.domain.state import build_snapshot
from server.tournament_agent.models import AgentProposal, ProposalStatus, TournamentAgentSession
from server.tournament_agent.policy import phase_rejection
from server.tournament_agent.privacy.display import resolve_player_tokens
from server.tournament_agent.services.proposals import (
    ProposalApplyError,
    apply_proposal,
    reject_proposal,
)
from server.tournament_agent.tools import (
    HANDLERS,
    READ_ONLY_TOOLS,
    TOOL_DEFINITIONS,
    dispatch_tool,
)
from server.tournament_agent.tools import ToolContext as AgentContext
from server.tournament_agent.tools.spirit import SPIRIT_BLOCKS

DEFINITIONS = {d["function"]["name"]: d["function"] for d in TOOL_DEFINITIONS}
LEFT_TO_HUB = {"propose_start_tournament", "propose_delete_stage", "propose_full_setup"}
READ_TOOLS = sorted(n for n in DEFINITIONS if n in READ_ONLY_TOOLS)
PROPOSE_TOOLS = sorted(
    n for n in DEFINITIONS if n.startswith("propose_") and n in HANDLERS and n not in LEFT_TO_HUB
)
REPORT_ROWS = 50
MATCH_UPS = {"M": "male", "F": "female"}

EVENT = {"event_slug": SLUG_SCHEMA}
ARGUMENTS = {"type": "object"}
OFF = "the tournament agent is switched off."
NOT_DIRECTOR = "you do not direct this tournament."


def _tournament(user: Any, event_slug: str) -> tuple[Tournament | None, ToolResult | None]:
    tournament = Tournament.objects.select_related("event").filter(event__slug=event_slug).first()
    if tournament is None:
        return None, fail("Tournament not found", hint="Use search to find the event_slug.")
    return tournament, _gate(user, tournament)


def _gate(user: Any, tournament: Tournament) -> ToolResult | None:
    if not settings.TOURNAMENT_AGENT_ENABLED:
        return refuse(OFF)
    if not can_manage_tournament(user, tournament):
        return refuse(NOT_DIRECTOR)
    return None


def _session(user: Any, tournament: Tournament) -> TournamentAgentSession:
    session, _ = TournamentAgentSession.objects.get_or_create(
        user=user, tournament=tournament, defaults={"model_id": default_model_id()}
    )
    return session


def _shown(tournament: Tournament, value: Any) -> Any:
    return resolve_player_tokens(value, tournament)


def _capped(result: Any) -> Any:
    lists = (
        [k for k, v in result.items() if isinstance(v, list)] if isinstance(result, dict) else []
    )
    if not lists:
        return result
    biggest = max(lists, key=lambda k: len(result[k]))
    return cap(result, list_key=biggest, hint="Ask for a narrower read, such as one match.")


def _run(ctx: ToolContext, args: dict[str, Any], allowed: list[str]) -> ToolResult:
    name = args["tool"]
    if name not in allowed:
        return fail(f"{name} is not one of: {', '.join(allowed)}")
    tournament, denied = _tournament(ctx.user, args["event_slug"])
    if tournament is None or denied:
        return denied or fail("Tournament not found")
    arguments = args.get("arguments", {})
    if problem := validate(arguments, DEFINITIONS[name]["parameters"]):
        return fail(problem, hint="list_director_tools shows each tool's parameters.")
    session = _session(ctx.user, tournament)
    phase = phase_for(build_snapshot(session))
    if rejection := phase_rejection(phase, name):
        return fail(rejection["message"], phase=rejection["phase"])
    result = dispatch_tool(AgentContext(session=session, tournament=tournament), name, arguments)
    if isinstance(result, dict) and result.get("error"):
        return fail(str(result["error"]))
    return ok({"tool": name, "phase": phase.value, "result": _capped(_shown(tournament, result))})


SAMPLES: dict[str, Any] = {"integer": 1, "number": 1, "boolean": True, "array": [], "object": {}}


def _sample(schema: dict[str, Any]) -> Any:
    if "enum" in schema:
        return schema["enum"][0]
    if schema.get("type") == "string":
        return "2026-01-01" if schema.get("format") == "date" else "text"
    return SAMPLES.get(str(schema.get("type")))


def _example(parameters: dict[str, Any]) -> dict[str, Any]:
    properties = parameters.get("properties", {})
    return {name: _sample(properties[name]) for name in parameters.get("required", [])}


@tool(
    "list_director_tools",
    title="List tournament agent tools",
    description=(
        "The tournament agent's read tools and change proposals, with what each does, its "
        "parameters and an example of the arguments. Use read_tournament_ops for a read and propose_tournament_change for a "
        "proposal."
    ),
    input_schema={"type": "object", "additionalProperties": False},
    audience=Audience.DIRECTOR,
)
def list_director_tools(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    rows = [
        {
            "tool": name,
            "kind": "read" if name in READ_ONLY_TOOLS else "proposal",
            "description": DEFINITIONS[name]["description"],
            "parameters": DEFINITIONS[name]["parameters"],
            "example": _example(DEFINITIONS[name]["parameters"]),
        }
        for name in READ_TOOLS + PROPOSE_TOOLS
    ]
    return ok({"tools": rows})


@tool(
    "read_tournament_ops",
    title="Read tournament operations",
    description=(
        "A director's agent reads (not the public schedule, which is get_tournament): run one of the tournament agent's read tools on a tournament you direct, such as "
        "list_matches, get_standings or list_fields. list_director_tools shows the tools and "
        "their arguments."
    ),
    input_schema={
        "type": "object",
        "properties": {
            **EVENT,
            "tool": {"type": "string", "enum": READ_TOOLS},
            "arguments": ARGUMENTS,
        },
        "required": ["event_slug", "tool"],
        "additionalProperties": False,
    },
    audience=Audience.DIRECTOR,
)
def read_tournament_ops(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    return _run(ctx, args, READ_TOOLS)


@tool(
    "propose_tournament_change",
    title="Propose a tournament change",
    description=(
        "Ask the tournament agent for a change, such as propose_match_score or "
        "propose_create_field; call list_director_tools first for the tool's argument schema. This only creates a pending proposal; nothing changes until "
        "confirm_tournament_proposal. Starting a tournament, deleting a stage and a full "
        "setup are done on Hub. One pending proposal per kind: confirm or reject it before proposing another of the same kind; a new one replaces the old, including ones made in Hub's tournament assistant."
    ),
    input_schema={
        "type": "object",
        "properties": {
            **EVENT,
            "tool": {"type": "string", "enum": PROPOSE_TOOLS},
            "arguments": ARGUMENTS,
        },
        "required": ["event_slug", "tool", "arguments"],
        "additionalProperties": False,
    },
    audience=Audience.DIRECTOR,
    writes=True,
)
def propose_tournament_change(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    result = _run(ctx, args, PROPOSE_TOOLS)
    if result.is_error:
        return result
    made = result.data["result"]
    return ok(
        {
            "tool": args["tool"],
            "proposal_id": made["proposal_id"],
            "status": made["status"],
            "summary": made["summary"],
        }
    )


def _proposals(user: Any, tournament: Tournament) -> Any:
    rows = AgentProposal.objects.filter(
        session__tournament=tournament, status=ProposalStatus.PENDING
    )
    return rows if user.is_superuser else rows.filter(session__user=user)


@tool(
    "list_tournament_proposals",
    title="List pending tournament proposals",
    description="The pending proposals on a tournament you direct, with proposal_id and summary.",
    input_schema={
        "type": "object",
        "properties": EVENT,
        "required": ["event_slug"],
        "additionalProperties": False,
    },
    audience=Audience.DIRECTOR,
)
def list_tournament_proposals(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    tournament, denied = _tournament(ctx.user, args["event_slug"])
    if tournament is None or denied:
        return denied or fail("Tournament not found")
    rows = [
        {
            "proposal_id": p.pk,
            "tool": p.tool_name,
            "summary": _shown(tournament, p.summary),
            "created_at": p.created_at.isoformat(),
        }
        for p in _proposals(ctx.user, tournament)
    ]
    return ok(cap({"proposals": rows}, list_key="proposals", hint="Reject old ones."))


def _mine(ctx: ToolContext, proposal_id: int) -> tuple[AgentProposal | None, ToolResult | None]:
    proposal = (
        AgentProposal.objects.select_related("session__tournament__event")
        .filter(pk=proposal_id)
        .first()
    )
    if proposal is None:
        return None, fail("Proposal not found")
    if proposal.session.user_id != ctx.user.pk and not ctx.user.is_superuser:
        return None, refuse("this is not your proposal.")
    return proposal, _gate(ctx.user, proposal.session.tournament)


PROPOSAL_ID = {"type": "object", "properties": {"proposal_id": {"type": "integer", "minimum": 1}}}


@tool(
    "confirm_tournament_proposal",
    title="Confirm a tournament proposal",
    description=(
        "Apply a pending proposal to the tournament: scores, schedule and standings change "
        "for real. Asks first."
    ),
    input_schema={**PROPOSAL_ID, "required": ["proposal_id"], "additionalProperties": False},
    audience=Audience.DIRECTOR,
    writes=True,
    destructive=True,
)
def confirm_tournament_proposal(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    proposal, denied = _mine(ctx, args["proposal_id"])
    if proposal is None or denied:
        return denied or fail("Proposal not found")
    tournament = proposal.session.tournament

    def apply() -> ToolResult:
        try:
            result = apply_proposal(proposal)
        except ProposalApplyError as error:
            return fail(str(error))
        return ok(
            {
                "proposal_id": proposal.pk,
                "applied": True,
                "result": _shown(tournament, result),
            }
        )

    return confirm_then(
        ctx,
        message=(
            f"Apply this change to {tournament.event.title}: "
            f"{_shown(tournament, proposal.summary)}. It changes the real tournament."
        ),
        binding=args,
        action=apply,
    )


@tool(
    "reject_tournament_proposal",
    title="Reject a tournament proposal",
    description="Turn down a pending proposal so it can no longer be confirmed.",
    input_schema={**PROPOSAL_ID, "required": ["proposal_id"], "additionalProperties": False},
    audience=Audience.DIRECTOR,
    writes=True,
    destructive=True,
)
def reject_tournament_proposal(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    proposal, denied = _mine(ctx, args["proposal_id"])
    if proposal is None or denied:
        return denied or fail("Proposal not found")
    try:
        reject_proposal(proposal)
    except ProposalApplyError as error:
        return fail(str(error))
    return ok({"proposal_id": proposal.pk, "rejected": True})


def _match_row(match: Match, **extra: Any) -> dict[str, Any]:
    return {
        "match_id": match.pk,
        "name": match.name,
        "time": match.time.isoformat() if match.time else None,
        "team_1": match.team_1.name if match.team_1 else None,
        "team_2": match.team_2.name if match.team_2 else None,
        **extra,
    }


def _roster_counts(event_id: int) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = {}
    rows = Registration.objects.filter(event_id=event_id, is_playing=True)
    for team_id, match_up in rows.values_list("team_id", "player__match_up"):
        row = counts.setdefault(team_id, {"total": 0, "male": 0, "female": 0})
        row["total"] += 1
        if match_up in MATCH_UPS:
            row[MATCH_UPS[match_up]] += 1
    return counts


def _under_minimum(tournament: Tournament) -> list[dict[str, Any]]:
    series = tournament.event.series
    if series is None:
        return []
    minimum = {
        "total": series.event_min_players_total,
        "male": series.event_min_players_male,
        "female": series.event_min_players_female,
    }
    counts = _roster_counts(tournament.event_id)
    ids = set(counts) | set(tournament.teams.values_list("pk", flat=True))
    names = dict(Team.objects.filter(pk__in=ids).values_list("pk", "name"))
    rows = []
    for team_id in sorted(ids):
        roster = counts.get(team_id, {"total": 0, "male": 0, "female": 0})
        if any(roster[k] < minimum[k] for k in minimum):
            rows.append(
                {"team_id": team_id, "name": names[team_id], "roster": roster, "minimum": minimum}
            )
    return rows


@tool(
    "get_tournament_ops_report",
    title="Tournament operations report",
    description=(
        "The director's gaps report (not a data read: see read_tournament_ops): what needs chasing on a tournament you direct: matches past their start with no score, "
        "score disagreements between captains, missing spirit scores, unscheduled matches, teams "
        "with players rostered but no payment, and teams under the series' roster minimums."
    ),
    input_schema={
        "type": "object",
        "properties": EVENT,
        "required": ["event_slug"],
        "additionalProperties": False,
    },
    audience=Audience.DIRECTOR,
)
def get_tournament_ops_report(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    tournament, denied = _tournament(ctx.user, args["event_slug"])
    if tournament is None or denied:
        return denied or fail("Tournament not found")
    matches = Match.objects.filter(tournament=tournament).select_related(
        "team_1",
        "team_2",
        "suggested_score_team_1",
        "suggested_score_team_2",
        *SPIRIT_BLOCKS.values(),
    )
    open_matches = matches.exclude(status=Match.Status.COMPLETED)
    paid = set(tournament.teams.values_list("pk", flat=True)) | set(
        tournament.partial_teams.values_list("pk", flat=True)
    )
    registered = Registration.objects.filter(event_id=tournament.event_id).values_list(
        "team_id", "team__name"
    )
    sections = {
        "unscored_matches": [_match_row(m) for m in open_matches.filter(time__lt=now())],
        "unscheduled_matches": [
            _match_row(m)
            for m in open_matches.filter(time__isnull=True)
            | open_matches.filter(field__isnull=True)
        ],
        "score_disagreements": [
            _match_row(m)
            for m in open_matches.filter(
                suggested_score_team_1__isnull=False, suggested_score_team_2__isnull=False
            )
            if not is_submitted_scores_equal(m)
        ],
        "missing_spirit": [
            _match_row(m, missing=[b for b, a in SPIRIT_BLOCKS.items() if getattr(m, a) is None])
            for m in matches.filter(status=Match.Status.COMPLETED)
            if any(getattr(m, a) is None for a in SPIRIT_BLOCKS.values())
        ],
        "unpaid_teams": [
            {"team_id": team_id, "name": name}
            for team_id, name in sorted(set(registered))
            if team_id not in paid
        ],
        "teams_under_minimum": _under_minimum(tournament),
    }
    report: dict[str, Any] = {
        "event_slug": tournament.event.slug,
        "counts": {k: len(v) for k, v in sections.items()},
    }
    for key, rows in sections.items():
        report[key] = rows[:REPORT_ROWS]
    if any(len(v) > REPORT_ROWS for v in sections.values()):
        report["truncated"] = f"Each list shows the first {REPORT_ROWS}; counts has the totals."
    return ok(report)
