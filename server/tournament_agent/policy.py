"""Which tools each phase may use, and the guard that enforces it.

Setup order used to be prompt rule 6, pool-before-schedule used to be rule 9, and
"never re-run the whole scheduler on a live event" used to be a paragraph in the
repair skill. All three are the same statement: some tools are not legal in some
states. Stating it once here means the model is handed a menu it cannot misuse,
instead of a long menu and a list of apologies for the parts it must not touch.

Two layers, because a model can emit a call from a schema it saw two rounds ago:
`tool_definitions_for` decides what is advertised, and `phase_rejection` decides
what is accepted.
"""

from __future__ import annotations

from typing import Any

from server.tournament_agent.domain.phase import PHASE_GUIDANCE, Phase
from server.tournament_agent.tools import HANDLERS, TOOL_DEFINITIONS

# --- read groups -----------------------------------------------------------

# Available in every phase: where am I, what exists, what is waiting on staff.
BASE_READS = frozenset(
    {
        "get_tournament_overview",
        "list_stages",
        "list_proposals",
        "list_fields",
        "list_matches",
        "list_teams_seeding",
    }
)
STRUCTURE_READS = frozenset(
    {
        "list_pools",
        "list_swiss_rounds",
        "list_brackets",
        "list_cross_pools",
        "list_position_pools",
    }
)
STANDINGS_READS = frozenset({"get_standings", "get_swiss_standings"})
SCHEDULE_READS = frozenset({"check_schedule_conflicts"})
SPIRIT_READS = frozenset(
    {
        "find_roster_player",
        "get_match_spirit",
        "list_missing_spirit_scores",
        "get_spirit_summary",
    }
)
ALL_READS = BASE_READS | STRUCTURE_READS | STANDINGS_READS | SCHEDULE_READS | SPIRIT_READS

# --- write groups ----------------------------------------------------------

FIELD_TOOLS = frozenset({"propose_create_field", "propose_update_field", "propose_delete_field"})
STAGE_TOOLS = frozenset(
    {
        "propose_pool_stage",
        "propose_create_pool",
        "propose_create_swiss_round",
        "propose_create_cross_pool",
        "propose_create_bracket",
        "propose_create_position_pool",
        "propose_create_cross_pool_matches",
        "propose_delete_stage",
        "propose_generate_fixtures",
        "propose_full_setup",
        "propose_update_seeding",
    }
)
# Placing a grid that does not exist yet. `propose_recommended_schedule` fills
# every empty slot at once, which is right during setup and wrong once games are
# being played.
SCHEDULE_TOOLS = frozenset({"propose_recommended_schedule", "propose_bulk_schedule"})
# Moving what is already placed — safe at any point after a schedule exists.
REPAIR_TOOLS = frozenset(
    {
        "propose_shift_schedule",
        "propose_update_match",
        "propose_update_match_seeds",
        "propose_delete_match",
    }
)
LIVE_TOOLS = frozenset({"propose_match_score", "propose_generate_fixtures"})
SPIRIT_TOOLS = frozenset({"propose_spirit_scores"})
START_TOOLS = frozenset({"propose_start_tournament"})

INTERACTION = frozenset({"ask_user"})


TOOLS_BY_PHASE: dict[Phase, frozenset[str]] = {
    # Nothing can be built on a tournament with nowhere to play.
    Phase.NO_FIELDS: BASE_READS | INTERACTION | FIELD_TOOLS,
    # Matches do not exist yet, so there is nothing to schedule or repair.
    # `propose_create_pool` is withheld here on purpose: building the stage goes
    # through `propose_pool_stage`, which derives the snake instead of trusting a
    # seed list the model wrote. Adding one more pool later is a NO_SCHEDULE job.
    Phase.NO_STAGES: (
        BASE_READS
        | STRUCTURE_READS
        | INTERACTION
        | FIELD_TOOLS
        | (STAGE_TOOLS - {"propose_create_pool"})
    ),
    Phase.NO_SCHEDULE: (
        BASE_READS
        | STRUCTURE_READS
        | SCHEDULE_READS
        | INTERACTION
        | FIELD_TOOLS
        | STAGE_TOOLS
        | SCHEDULE_TOOLS
        | REPAIR_TOOLS
    ),
    Phase.READY: (
        BASE_READS
        | STRUCTURE_READS
        | SCHEDULE_READS
        | STANDINGS_READS
        | INTERACTION
        | FIELD_TOOLS
        | STAGE_TOOLS
        | SCHEDULE_TOOLS
        | REPAIR_TOOLS
        | START_TOOLS
    ),
    # No stage creation and no whole-grid scheduler: a live event is repaired one
    # match at a time. `propose_generate_fixtures` stays — it is how a bracket
    # gets its teams once the pools that feed it have finished.
    Phase.LIVE: (
        ALL_READS
        | INTERACTION
        | LIVE_TOOLS
        | REPAIR_TOOLS
        | SPIRIT_TOOLS
        | SPIRIT_READS
        # Not propose_update_seeding: update_tournament_seeding refuses once the
        # tournament is live, so offering it here only ever produces a card that
        # fails on Confirm.
        | {"propose_delete_stage"}
        | FIELD_TOOLS
    ),
    Phase.COMPLETE: ALL_READS,
}


def tools_for(phase: Phase) -> frozenset[str]:
    return TOOLS_BY_PHASE[phase]


def tool_definitions_for(phase: Phase) -> list[dict[str, Any]]:
    """The tool schemas this phase advertises.

    Sending all of them costs about 4,300 tokens on every round of every turn; a
    setup phase needs roughly a quarter of that, and the gap widens with each tool
    added.
    """
    allowed = tools_for(phase)
    return [
        definition
        for definition in TOOL_DEFINITIONS
        if ((definition.get("function") or definition).get("name") or "") in allowed
    ]


def phase_rejection(phase: Phase, name: str) -> dict[str, str] | None:
    """The tool result for a call this phase does not allow, or None when it does.

    Phrased as the next legal step rather than a refusal: the model has to be able
    to recover inside the same turn.
    """
    if name in tools_for(phase) or name not in HANDLERS:
        return None
    message = (
        f"`{name}` is not available right now. {PHASE_GUIDANCE[phase]} "
        f"Use one of: {', '.join(sorted(tools_for(phase)))}."
    )
    return {"error": message, "message": message, "phase": phase.value}


def _unreachable_tools() -> set[str]:
    """Handlers no phase can call — a tool added without a home is a dead tool."""
    reachable: set[str] = set()
    for names in TOOLS_BY_PHASE.values():
        reachable |= set(names)
    return set(HANDLERS) - reachable


def _unknown_tools() -> set[str]:
    """Names in the phase table that no handler backs — a typo, or a removed tool."""
    named: set[str] = set()
    for names in TOOLS_BY_PHASE.values():
        named |= set(names)
    return named - set(HANDLERS)
