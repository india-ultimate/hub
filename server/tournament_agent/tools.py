"""Tournament agent tools: reads, ask_user, and proposal creators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Q

from server.core.models import Team
from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    Pool,
    PositionPool,
    SwissRound,
    Tournament,
    TournamentField,
)
from server.tournament_agent.mask import assert_safe_tool_payload, scrub_json_strings
from server.tournament_agent.models import (
    AgentProposal,
    AgentQuestion,
    ProposalStatus,
    QuestionSelectionMode,
    QuestionStatus,
    TournamentAgentMessage,
    TournamentAgentSession,
)

ToolHandler = Callable[..., Any]

_EMPTY_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def _team_map(tournament: Tournament) -> dict[int, str]:
    ids = set()
    for seed_map in (tournament.initial_seeding or {}, tournament.current_seeding or {}):
        for tid in seed_map.values():
            try:
                ids.add(int(tid))
            except (TypeError, ValueError):
                continue
    teams = Team.objects.filter(id__in=ids).only("id", "name")
    return {t.id: t.name for t in teams}


def _safe(result: Any) -> Any:
    scrubbed = scrub_json_strings(result)
    assert_safe_tool_payload(scrubbed)
    return scrubbed


class AskUserPause(Exception):
    """Raised when ask_user creates a pending question and the agent loop should stop."""

    def __init__(self, question: AgentQuestion) -> None:
        self.question = question
        super().__init__("Waiting for user answer")


class ToolContext:
    def __init__(
        self,
        session: TournamentAgentSession,
        tournament: Tournament,
        assistant_message: TournamentAgentMessage | None = None,
    ) -> None:
        self.session = session
        self.tournament = tournament
        self.assistant_message = assistant_message

    def create_proposal(self, tool_name: str, summary: str, payload: dict[str, Any]) -> dict[str, Any]:
        proposal = AgentProposal.objects.create(
            session=self.session,
            tool_name=tool_name,
            summary=summary,
            payload=payload,
            status=ProposalStatus.PENDING,
            created_by_message=self.assistant_message,
        )
        return _safe(
            {
                "proposal_id": proposal.id,
                "status": proposal.status,
                "summary": summary,
                "message": "Proposal created. Staff must Confirm in the UI before anything is applied.",
            }
        )


def get_tournament_overview(ctx: ToolContext) -> dict[str, Any]:
    t = ctx.tournament
    event = t.event
    matches = Match.objects.filter(tournament=t)
    return _safe(
        {
            "tournament_id": t.id,
            "title": event.title,
            "slug": event.slug or "",
            "status": t.status,
            "team_count": t.teams.count(),
            "pool_count": Pool.objects.filter(tournament=t).count(),
            "swiss_count": SwissRound.objects.filter(tournament=t).count(),
            "bracket_count": Bracket.objects.filter(tournament=t).count(),
            "cross_pool_count": CrossPool.objects.filter(tournament=t).count(),
            "position_pool_count": PositionPool.objects.filter(tournament=t).count(),
            "field_count": TournamentField.objects.filter(tournament=t).count(),
            "match_count": matches.count(),
            "unscheduled_match_count": matches.filter(
                Q(time__isnull=True) | Q(field__isnull=True)
            ).count(),
            "start_date": str(event.start_date),
            "end_date": str(event.end_date),
        }
    )


def list_teams_seeding(ctx: ToolContext) -> dict[str, Any]:
    t = ctx.tournament
    names = _team_map(t)
    seeding = []
    for seed_str, team_id in sorted((t.initial_seeding or {}).items(), key=lambda x: int(x[0])):
        tid = int(team_id)
        seeding.append({"seed": int(seed_str), "team_id": tid, "team_name": names.get(tid, "")})
    return _safe({"seeding": seeding})


def list_pools(ctx: ToolContext) -> dict[str, Any]:
    names = _team_map(ctx.tournament)
    pools = []
    for pool in Pool.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        seeds = []
        for seed, team_id in sorted((pool.initial_seeding or {}).items(), key=lambda x: int(x[0])):
            tid = int(team_id)
            seeds.append({"seed": int(seed), "team_id": tid, "team_name": names.get(tid, "")})
        standings = []
        for team_id, row in (pool.results or {}).items():
            tid = int(team_id)
            standings.append(
                {
                    "team_id": tid,
                    "team_name": names.get(tid, ""),
                    "rank": row.get("rank"),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "draws": row.get("draws"),
                    "GF": row.get("GF"),
                    "GA": row.get("GA"),
                }
            )
        pools.append(
            {
                "id": pool.id,
                "name": pool.name,
                "sequence_number": pool.sequence_number,
                "seeding": seeds,
                "standings": standings,
            }
        )
    return _safe({"pools": pools})


def list_swiss_rounds(ctx: ToolContext) -> dict[str, Any]:
    rounds = []
    for sw in SwissRound.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        rounds.append(
            {
                "id": sw.id,
                "name": sw.name,
                "sequence_number": sw.sequence_number,
                "num_rounds": sw.num_rounds,
                "current_round": sw.current_round,
                "initial_seeding": sw.initial_seeding,
            }
        )
    return _safe({"swiss_rounds": rounds})


def list_brackets(ctx: ToolContext) -> dict[str, Any]:
    brackets = []
    for b in Bracket.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        brackets.append(
            {
                "id": b.id,
                "name": b.name,
                "sequence_number": b.sequence_number,
                "initial_seeding": b.initial_seeding,
                "current_seeding": b.current_seeding,
            }
        )
    return _safe({"brackets": brackets})


def list_cross_pools(ctx: ToolContext) -> dict[str, Any]:
    items = []
    for cp in CrossPool.objects.filter(tournament=ctx.tournament):
        items.append(
            {
                "id": cp.id,
                "initial_seeding": cp.initial_seeding,
                "current_seeding": cp.current_seeding,
            }
        )
    return _safe({"cross_pools": items})


def list_position_pools(ctx: ToolContext) -> dict[str, Any]:
    items = []
    for pp in PositionPool.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        items.append(
            {
                "id": pp.id,
                "name": pp.name,
                "sequence_number": pp.sequence_number,
                "initial_seeding": pp.initial_seeding,
            }
        )
    return _safe({"position_pools": items})


def list_fields(ctx: ToolContext) -> dict[str, Any]:
    fields = [
        {"id": f.id, "name": f.name, "is_broadcasted": f.is_broadcasted}
        for f in TournamentField.objects.filter(tournament=ctx.tournament).order_by("name")
    ]
    return _safe({"fields": fields})


def list_matches(
    ctx: ToolContext,
    unscheduled_only: bool = False,
    stage: str | None = None,
) -> dict[str, Any]:
    qs = Match.objects.filter(tournament=ctx.tournament).select_related(
        "field", "team_1", "team_2", "pool", "bracket", "swiss_round", "position_pool", "cross_pool"
    )
    if unscheduled_only:
        qs = qs.filter(Q(time__isnull=True) | Q(field__isnull=True))
    if stage == "pool":
        qs = qs.exclude(pool__isnull=True)
    elif stage == "bracket":
        qs = qs.exclude(bracket__isnull=True)
    elif stage == "swiss":
        qs = qs.exclude(swiss_round__isnull=True)
    elif stage == "cross_pool":
        qs = qs.exclude(cross_pool__isnull=True)
    elif stage == "position_pool":
        qs = qs.exclude(position_pool__isnull=True)

    matches = []
    for m in qs.order_by("time", "id"):
        matches.append(
            {
                "id": m.id,
                "name": m.name,
                "status": m.status,
                "time": m.time.isoformat() if m.time else None,
                "duration_mins": m.duration_mins,
                "field_id": m.field_id,
                "field_name": m.field.name if m.field else None,
                "team_1_id": m.team_1_id,
                "team_1_name": m.team_1.name if m.team_1 else None,
                "team_2_id": m.team_2_id,
                "team_2_name": m.team_2.name if m.team_2 else None,
                "placeholder_seed_1": m.placeholder_seed_1,
                "placeholder_seed_2": m.placeholder_seed_2,
                "score_team_1": m.score_team_1,
                "score_team_2": m.score_team_2,
                "pool": m.pool.name if m.pool else None,
                "bracket": m.bracket.name if m.bracket else None,
                "swiss_round": m.swiss_round.name if m.swiss_round else None,
            }
        )
    return _safe({"matches": matches, "count": len(matches)})


def get_standings(ctx: ToolContext) -> dict[str, Any]:
    return _safe(
        {
            "pools": list_pools(ctx)["pools"],
            "current_seeding": ctx.tournament.current_seeding,
        }
    )


def get_schedule_grid(ctx: ToolContext) -> dict[str, Any]:
    return list_matches(ctx, unscheduled_only=False)


def ask_user(
    ctx: ToolContext,
    prompt: str,
    selection_mode: str,
    options: list[dict[str, Any]],
    allow_other: bool = False,
    allow_skip: bool = False,
    context: str = "",
) -> dict[str, Any]:
    if selection_mode not in (QuestionSelectionMode.SINGLE, QuestionSelectionMode.MULTI):
        return {"error": "selection_mode must be 'single' or 'multi'"}
    if not (2 <= len(options) <= 8):
        return {"error": "options must be a list of 2–8 items with id and label"}
    clean_opts = []
    for opt in options:
        if "id" not in opt or "label" not in opt:
            return {"error": "each option needs id and label"}
        clean_opts.append(
            {
                "id": str(opt["id"]),
                "label": str(opt["label"]),
                "description": str(opt.get("description") or ""),
            }
        )

    AgentQuestion.objects.filter(session=ctx.session, status=QuestionStatus.PENDING).update(
        status=QuestionStatus.SUPERSEDED
    )
    question = AgentQuestion.objects.create(
        session=ctx.session,
        prompt=prompt,
        context=context,
        selection_mode=selection_mode,
        options=clean_opts,
        allow_other=bool(allow_other),
        allow_skip=bool(allow_skip),
        status=QuestionStatus.PENDING,
        created_by_message=ctx.assistant_message,
    )
    raise AskUserPause(question)


def propose_create_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_pool",
        f"Create pool {name} with seeds {seeding}",
        {"name": name, "sequence_number": sequence_number, "seeding": seeding},
    )


def propose_create_swiss_round(
    ctx: ToolContext, name: str, seeding: list[int], num_rounds: int, sequence_number: int = 1
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_swiss_round",
        f"Create Swiss group {name} ({num_rounds} rounds) with seeds {seeding}",
        {
            "name": name,
            "seeding": seeding,
            "num_rounds": num_rounds,
            "sequence_number": sequence_number,
        },
    )


def propose_create_cross_pool(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal("propose_create_cross_pool", "Create cross pool stage", {})


def propose_create_bracket(ctx: ToolContext, name: str, sequence_number: int) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_bracket",
        f"Create bracket {name}",
        {"name": name, "sequence_number": sequence_number},
    )


def propose_create_position_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_position_pool",
        f"Create position pool {name} with seeds {seeding}",
        {"name": name, "sequence_number": sequence_number, "seeding": seeding},
    )


def propose_create_field(
    ctx: ToolContext,
    name: str,
    address: str | None = None,
    is_broadcasted: bool = False,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_field",
        f"Create field '{name.strip()}'",
        {"name": name.strip(), "address": address, "is_broadcasted": is_broadcasted},
    )


def propose_create_cross_pool_matches(
    ctx: ToolContext, seed_pairs: list[list[int]], sequence_number: int = 1
) -> dict[str, Any]:
    pairs = [[int(pair[0]), int(pair[1])] for pair in seed_pairs]
    summary_pairs = ", ".join(f"{a} v {b}" for a, b in pairs)
    return ctx.create_proposal(
        "propose_create_cross_pool_matches",
        f"Create {len(pairs)} cross pool matches (round {sequence_number}): {summary_pairs}",
        {"seed_pairs": pairs, "sequence_number": sequence_number},
    )


def propose_update_seeding(ctx: ToolContext, seeding: dict[str, int]) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_update_seeding",
        "Update tournament seeding",
        {"seeding": seeding},
    )


def propose_update_match(
    ctx: ToolContext,
    match_id: int,
    time: str | None = None,
    field_id: int | None = None,
    duration_mins: int | None = None,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_update_match",
        f"Update match {match_id}",
        {
            "match_id": match_id,
            "time": time,
            "field_id": field_id,
            "duration_mins": duration_mins,
        },
    )


def propose_delete_match(ctx: ToolContext, match_id: int) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_delete_match",
        f"Delete match {match_id}",
        {"match_id": match_id},
    )


def propose_bulk_schedule(
    ctx: ToolContext, assignments: list[dict[str, Any]]
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_bulk_schedule",
        f"Schedule {len(assignments)} matches",
        {"assignments": assignments},
    )


def propose_start_tournament(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal("propose_start_tournament", "Start tournament (assign pool/Swiss teams)", {})


def propose_generate_fixtures(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_generate_fixtures",
        "Populate fixtures / advance bracket stages",
        {},
    )


def propose_full_setup(
    ctx: ToolContext,
    format: str,
    pool_defs: list[dict[str, Any]] | None = None,
    swiss_defs: list[dict[str, Any]] | None = None,
    bracket_names: list[str] | None = None,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_full_setup",
        f"Full setup using format={format}",
        {
            "format": format,
            "pool_defs": pool_defs or [],
            "swiss_defs": swiss_defs or [],
            "bracket_names": bracket_names or [],
        },
    )


def propose_recommended_schedule(
    ctx: ToolContext,
    start_date: str,
    end_date: str | None = None,
    duration_mins: int = 75,
    min_rest_mins: int = 60,
    day_start_hour: int = 9,
    day_end_hour: int = 18,
    lunch_start_hour: int | None = 13,
    lunch_end_hour: int | None = 14,
    field_ids: list[int] | None = None,
) -> dict[str, Any]:
    from server.tournament_agent.scheduler import recommend_schedule

    result = recommend_schedule(
        tournament=ctx.tournament,
        start_date=start_date,
        end_date=end_date,
        duration_mins=duration_mins,
        min_rest_mins=min_rest_mins,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
        lunch_start_hour=lunch_start_hour,
        lunch_end_hour=lunch_end_hour,
        field_ids=field_ids,
    )
    assignments = result["assignments"]
    return ctx.create_proposal(
        "propose_bulk_schedule",
        f"Recommended schedule for {len(assignments)} matches ({result.get('notes', '')})",
        {"assignments": assignments, "meta": result.get("meta", {})},
    )


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_tournament_overview",
            "description": "Get high-level tournament status and counts.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_teams_seeding",
            "description": "List teams with seed numbers.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pools",
            "description": "List pools with seeding and standings.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_swiss_rounds",
            "description": "List Swiss groups.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_brackets",
            "description": "List brackets.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_cross_pools",
            "description": "List cross pools.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_position_pools",
            "description": "List position pools.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_fields",
            "description": "List tournament fields.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_matches",
            "description": "List matches. Optionally only unscheduled or filter by stage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "unscheduled_only": {"type": "boolean"},
                    "stage": {
                        "type": "string",
                        "enum": ["pool", "bracket", "swiss", "cross_pool", "position_pool"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_standings",
            "description": "Get pool standings and current seeding.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedule_grid",
            "description": "Get all matches as a schedule grid.",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Ask the staff user a clarifying single- or multi-choice question. "
                "Use whenever format, duration, days, fields, or bracket size is ambiguous. "
                "Do not guess irreversible choices."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "selection_mode": {"type": "string", "enum": ["single", "multi"]},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["id", "label"],
                        },
                    },
                    "allow_other": {"type": "boolean"},
                    "allow_skip": {"type": "boolean"},
                    "context": {"type": "string"},
                },
                "required": ["prompt", "selection_mode", "options"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_pool",
            "description": "Propose creating a pool (requires staff Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sequence_number": {"type": "integer"},
                    "seeding": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["name", "sequence_number", "seeding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_swiss_round",
            "description": "Propose creating a Swiss group (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "seeding": {"type": "array", "items": {"type": "integer"}},
                    "num_rounds": {"type": "integer"},
                    "sequence_number": {"type": "integer"},
                },
                "required": ["name", "seeding", "num_rounds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_cross_pool",
            "description": "Propose creating a cross pool (requires Confirm).",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_bracket",
            "description": "Propose creating a bracket like '1-8' (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sequence_number": {"type": "integer"},
                },
                "required": ["name", "sequence_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_position_pool",
            "description": "Propose creating a position pool (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sequence_number": {"type": "integer"},
                    "seeding": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["name", "sequence_number", "seeding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_field",
            "description": (
                "Propose adding a playing field to the tournament, e.g. 'Field 3' "
                "(requires Confirm)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "is_broadcasted": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_cross_pool_matches",
            "description": (
                "Propose cross pool matches as seed pairs, e.g. [[1,3],[2,4],[5,12]] "
                "(requires Confirm). The cross pool stage must exist first "
                "(propose_create_cross_pool). Use sequence_number 2 for a second "
                "cross pool round."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seed_pairs": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                    "sequence_number": {"type": "integer"},
                },
                "required": ["seed_pairs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_seeding",
            "description": "Propose updating seed->team_id map (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {"seeding": {"type": "object"}},
                "required": ["seeding"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_match",
            "description": "Propose updating a match time/field/duration (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "match_id": {"type": "integer"},
                    "time": {"type": "string"},
                    "field_id": {"type": "integer"},
                    "duration_mins": {"type": "integer"},
                },
                "required": ["match_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_match",
            "description": "Propose deleting a match (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {"match_id": {"type": "integer"}},
                "required": ["match_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_schedule",
            "description": "Propose bulk time/field assignments (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "assignments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "match_id": {"type": "integer"},
                                "time": {"type": "string"},
                                "field_id": {"type": "integer"},
                                "duration_mins": {"type": "integer"},
                            },
                            "required": ["match_id", "time", "field_id"],
                        },
                    }
                },
                "required": ["assignments"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_start_tournament",
            "description": "Propose starting the tournament (requires Confirm).",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_generate_fixtures",
            "description": "Propose populating fixtures / advancing stages (requires Confirm).",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_full_setup",
            "description": "Propose a full structure setup recipe (requires Confirm).",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {"type": "string"},
                    "pool_defs": {"type": "array"},
                    "swiss_defs": {"type": "array"},
                    "bracket_names": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["format"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_recommended_schedule",
            "description": (
                "Run the deterministic scheduler and propose a bulk schedule (requires Confirm)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "duration_mins": {"type": "integer"},
                    "min_rest_mins": {"type": "integer"},
                    "day_start_hour": {"type": "integer"},
                    "day_end_hour": {"type": "integer"},
                    "lunch_start_hour": {"type": "integer"},
                    "lunch_end_hour": {"type": "integer"},
                    "field_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["start_date"],
            },
        },
    },
]

HANDLERS: dict[str, ToolHandler] = {
    "get_tournament_overview": get_tournament_overview,
    "list_teams_seeding": list_teams_seeding,
    "list_pools": list_pools,
    "list_swiss_rounds": list_swiss_rounds,
    "list_brackets": list_brackets,
    "list_cross_pools": list_cross_pools,
    "list_position_pools": list_position_pools,
    "list_fields": list_fields,
    "list_matches": list_matches,
    "get_standings": get_standings,
    "get_schedule_grid": get_schedule_grid,
    "ask_user": ask_user,
    "propose_create_pool": propose_create_pool,
    "propose_create_swiss_round": propose_create_swiss_round,
    "propose_create_cross_pool": propose_create_cross_pool,
    "propose_create_bracket": propose_create_bracket,
    "propose_create_position_pool": propose_create_position_pool,
    "propose_create_field": propose_create_field,
    "propose_create_cross_pool_matches": propose_create_cross_pool_matches,
    "propose_update_seeding": propose_update_seeding,
    "propose_update_match": propose_update_match,
    "propose_delete_match": propose_delete_match,
    "propose_bulk_schedule": propose_bulk_schedule,
    "propose_start_tournament": propose_start_tournament,
    "propose_generate_fixtures": propose_generate_fixtures,
    "propose_full_setup": propose_full_setup,
    "propose_recommended_schedule": propose_recommended_schedule,
}


def dispatch_tool(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> Any:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    return handler(ctx, **arguments)
