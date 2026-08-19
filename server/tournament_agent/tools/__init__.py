"""The tool surface the model is given, and the registry that dispatches it.

Everything the agent can do passes through `HANDLERS`. Reads answer questions,
proposals ask staff to approve a change, and `ask_user` hands the turn back — no
tool writes to the tournament itself; `services.proposals` does that on Confirm.

Import tools from this package, not from the modules beneath it: the split into
`reads` / `mutations` / `spirit` is for people editing them, and moving a tool
between those files should not ripple out to callers.
"""

from __future__ import annotations

import inspect
from typing import Any

from server.tournament_agent.tools.context import ToolContext, ToolHandler
from server.tournament_agent.tools.definitions import TOOL_DEFINITIONS
from server.tournament_agent.tools.interaction import AskUserPause, ask_user
from server.tournament_agent.tools.mutations import (
    propose_bulk_schedule,
    propose_create_bracket,
    propose_create_cross_pool,
    propose_create_cross_pool_matches,
    propose_create_field,
    propose_create_pool,
    propose_create_position_pool,
    propose_create_swiss_round,
    propose_delete_field,
    propose_delete_match,
    propose_delete_stage,
    propose_full_setup,
    propose_generate_fixtures,
    propose_match_score,
    propose_recommended_schedule,
    propose_shift_schedule,
    propose_start_tournament,
    propose_update_field,
    propose_update_match,
    propose_update_match_seeds,
    propose_update_seeding,
)
from server.tournament_agent.tools.queries import (
    STAGE_FIELDS,
    STAGE_MODELS,
    match_queryset,
)
from server.tournament_agent.tools.reads import (
    check_schedule_conflicts,
    get_standings,
    get_swiss_standings,
    get_tournament_overview,
    list_brackets,
    list_cross_pools,
    list_fields,
    list_matches,
    list_pools,
    list_position_pools,
    list_proposals,
    list_stages,
    list_swiss_rounds,
    list_teams_seeding,
)
from server.tournament_agent.tools.spirit import (
    SPIRIT_BLOCKS,
    find_roster_player,
    get_match_spirit,
    get_spirit_summary,
    list_missing_spirit_scores,
    propose_spirit_scores,
)

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
    "list_proposals": list_proposals,
    "get_standings": get_standings,
    "get_swiss_standings": get_swiss_standings,
    "list_stages": list_stages,
    "check_schedule_conflicts": check_schedule_conflicts,
    "find_roster_player": find_roster_player,
    "get_match_spirit": get_match_spirit,
    "list_missing_spirit_scores": list_missing_spirit_scores,
    "get_spirit_summary": get_spirit_summary,
    "ask_user": ask_user,
    "propose_create_pool": propose_create_pool,
    "propose_create_swiss_round": propose_create_swiss_round,
    "propose_create_cross_pool": propose_create_cross_pool,
    "propose_create_bracket": propose_create_bracket,
    "propose_create_position_pool": propose_create_position_pool,
    "propose_create_field": propose_create_field,
    "propose_update_field": propose_update_field,
    "propose_delete_field": propose_delete_field,
    "propose_create_cross_pool_matches": propose_create_cross_pool_matches,
    "propose_update_seeding": propose_update_seeding,
    "propose_update_match": propose_update_match,
    "propose_update_match_seeds": propose_update_match_seeds,
    "propose_delete_match": propose_delete_match,
    "propose_bulk_schedule": propose_bulk_schedule,
    "propose_match_score": propose_match_score,
    "propose_spirit_scores": propose_spirit_scores,
    "propose_shift_schedule": propose_shift_schedule,
    "propose_delete_stage": propose_delete_stage,
    "propose_start_tournament": propose_start_tournament,
    "propose_generate_fixtures": propose_generate_fixtures,
    "propose_full_setup": propose_full_setup,
    "propose_recommended_schedule": propose_recommended_schedule,
}

# Derived rather than listed: every read tool added since has to show up here, or a
# turn that used it silently behaves differently from a turn that did not.
READ_ONLY_TOOLS = frozenset(
    name for name in HANDLERS if not name.startswith("propose_") and name != "ask_user"
)


# The model copies keys from the last read. list_stages returns `id` not
# `stage_id`, and the repair skill used to say `kind` instead of `stage`.
# Remap those aliases so a delete-stage call still becomes a proposal.
_ARG_ALIASES: dict[str, dict[str, str]] = {
    "propose_delete_stage": {
        "kind": "stage",
        "stage_kind": "stage",
        "id": "stage_id",
    },
    "propose_update_field": {"id": "field_id"},
    "propose_delete_field": {"id": "field_id"},
}


def dispatch_tool(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> Any:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    args = dict(arguments or {})
    for src, dest in _ARG_ALIASES.get(name, {}).items():
        if dest not in args and src in args:
            args[dest] = args[src]
        args.pop(src, None)
    accepted = {
        key
        for key, param in inspect.signature(handler).parameters.items()
        if key != "ctx" and param.kind != inspect.Parameter.VAR_KEYWORD
    }
    return handler(ctx, **{key: value for key, value in args.items() if key in accepted})


__all__ = [
    "HANDLERS",
    "READ_ONLY_TOOLS",
    "SPIRIT_BLOCKS",
    "STAGE_FIELDS",
    "STAGE_MODELS",
    "TOOL_DEFINITIONS",
    "AskUserPause",
    "ToolContext",
    "ToolHandler",
    "ask_user",
    "check_schedule_conflicts",
    "dispatch_tool",
    "find_roster_player",
    "get_match_spirit",
    "get_spirit_summary",
    "get_standings",
    "get_swiss_standings",
    "get_tournament_overview",
    "list_brackets",
    "list_cross_pools",
    "list_fields",
    "list_matches",
    "list_missing_spirit_scores",
    "list_pools",
    "list_position_pools",
    "list_proposals",
    "list_stages",
    "list_swiss_rounds",
    "list_teams_seeding",
    "match_queryset",
    "propose_bulk_schedule",
    "propose_create_bracket",
    "propose_create_cross_pool",
    "propose_create_cross_pool_matches",
    "propose_create_field",
    "propose_create_pool",
    "propose_create_position_pool",
    "propose_create_swiss_round",
    "propose_delete_field",
    "propose_delete_match",
    "propose_delete_stage",
    "propose_full_setup",
    "propose_generate_fixtures",
    "propose_match_score",
    "propose_recommended_schedule",
    "propose_shift_schedule",
    "propose_spirit_scores",
    "propose_start_tournament",
    "propose_update_field",
    "propose_update_match",
    "propose_update_match_seeds",
    "propose_update_seeding",
]
