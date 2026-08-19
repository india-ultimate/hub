"""The JSON schemas the model actually sees.

Kept apart from the handlers because this is the contract: a parameter a handler
grows but this file never declares is stripped or rejected by providers that
validate arguments, and the tool then quietly ignores it. `ToolContractTests`
asserts the two stay in step.
"""

from __future__ import annotations

from typing import Any

_EMPTY_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

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
            "description": (
                "List teams with seed numbers, plus snake_draft pool assignments. "
                "Always use snake_draft when creating pools — never sequential blocks "
                "like 1-4 vs 5-8."
            ),
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
            "description": (
                "List matches. Filter as narrowly as the request allows: by stage, by "
                "status, by day (YYYY-MM-DD), by team, or only the ones still missing a "
                "time or field."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unscheduled_only": {"type": "boolean"},
                    "stage": {
                        "type": "string",
                        "enum": ["pool", "bracket", "swiss", "cross_pool", "position_pool"],
                    },
                    "status": {
                        "type": "string",
                        "enum": ["YTF", "SCH", "COM"],
                        "description": "Yet To Fix, Scheduled, or Completed.",
                    },
                    "day": {"type": "string", "description": "A single day, as YYYY-MM-DD."},
                    "team_id": {
                        "type": "integer",
                        "description": "Only matches this team plays, on either side.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_standings",
            "description": (
                "Get standings for every stage (pools, Swiss, position pools), plus bracket "
                "and tournament current seeding with team names."
            ),
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_swiss_standings",
            "description": (
                "Swiss group tables with rank, points, opponent strength and which team had "
                "the bye each round."
            ),
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_stages",
            "description": (
                "Every stage with match counts, how many are completed, whether the stage is "
                "finished, and its first/last match time. Use this to answer 'where are we?' "
                "in one call instead of listing each stage type."
            ),
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_proposals",
            "description": (
                "The proposals staff can actually Confirm, from the database. Chat that "
                "mentions a proposal number is not proof it exists — call this before "
                "telling staff one is pending. Pass proposal_id to look up a specific "
                "number (missing, expired, confirmed, or still pending)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "proposal_id": {
                        "type": "integer",
                        "description": "Look up this id even if it is not pending.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_roster_player",
            "description": (
                "Find a player on a team's roster by name and get their id back. You never "
                "receive names, emails or phone numbers — only ids. When more than one player "
                "matches, ask_user with '{{player:<id>}}' as each option label; staff see the "
                "real name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "integer"},
                    "query": {"type": "string", "description": "Name as staff wrote it"},
                },
                "required": ["team_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_match_spirit",
            "description": (
                "Spirit scores recorded for one match: the score each team received and each "
                "team's self score, with MVP/MSP as player ids."
            ),
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
            "name": "list_missing_spirit_scores",
            "description": (
                "Played matches that are still missing spirit blocks — use this to tell staff "
                "who they still need to chase."
            ),
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_spirit_summary",
            "description": "Tournament spirit ranking by team (points, self points, rank).",
            "parameters": _EMPTY_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_spirit_scores",
            "description": (
                "Propose recording spirit scores for a match (requires Confirm). Each block is "
                "{rules, fouls, fair, positive, communication} each scored 0-4, plus optional "
                "mvp_id/msp_id (received blocks only) and comments. 'team_1_received' is the "
                "score team 1 was GIVEN by team 2; 'team_1_self' is team 1 rating itself. The "
                "tournament spirit ranking only counts a match for a team once BOTH its "
                "received and self blocks exist, so enter all four when you have them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "match_id": {"type": "integer"},
                    "team_1_received": {"type": "object"},
                    "team_2_received": {"type": "object"},
                    "team_1_self": {"type": "object"},
                    "team_2_self": {"type": "object"},
                },
                "required": ["match_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_schedule_conflicts",
            "description": (
                "Audit the schedule: double-booked fields, teams playing two matches at once, "
                "rest below the minimum, stages starting before the stage feeding them ends, "
                "matches past the day window, and per-field/per-team daily load. Run this "
                "before and after any schedule repair."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_rest_mins": {"type": "integer"},
                    "day_end_hour": {"type": "integer"},
                    "day": {"type": "string", "description": "YYYY-MM-DD to check one day only"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": (
                "Ask the staff user a clarifying single- or multi-choice question. "
                "Use whenever format, duration, days, fields, or bracket size is ambiguous. "
                "Do not guess irreversible choices. Staff can always type their own answer; "
                "if they skip, do not ask the same question again."
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
            "description": (
                "Propose creating a pool (requires staff Confirm). seeding must be a "
                "snake-draft slice from list_teams_seeding.snake_draft, never a sequential "
                "block. Two pools of 4: A=[1,4,5,8] B=[2,3,6,7]."
            ),
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
            "description": (
                "Propose creating a bracket like '1-4' or '1-8' (requires Confirm). "
                "The name is a seed range; Confirm creates the full placement tree, "
                "not just semis and a final. A 1-4 is 1v4 and 2v3 (semis), 1v2 (final), "
                "AND 3v4 (3rd place / push-in). Do not also create a 3-4 bracket for that "
                "game, and do not describe a 1-4 as two semis and a final."
            ),
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
            "name": "propose_update_field",
            "description": (
                "Propose renaming a field or changing its address / broadcast flag "
                "(requires Confirm). Look up field_id with list_fields first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "is_broadcasted": {"type": "boolean"},
                },
                "required": ["field_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_field",
            "description": (
                "Propose deleting a playing field (requires Confirm). Refused if any "
                "match is still assigned to it — move those matches first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "integer"},
                },
                "required": ["field_id"],
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
            "description": (
                "Propose updating one match's time, field, duration, or placeholder "
                "seeds (requires Confirm). To rewrite several bracket pairings at "
                "once (3v5 and 4v6 instead of 3v6 and 4v5), use "
                "propose_update_match_seeds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "match_id": {"type": "integer"},
                    "time": {"type": "string"},
                    "field_id": {"type": "integer"},
                    "duration_mins": {"type": "integer"},
                    "seed_1": {
                        "type": "integer",
                        "description": "New placeholder seed for side 1. Pass with seed_2.",
                    },
                    "seed_2": {
                        "type": "integer",
                        "description": "New placeholder seed for side 2. Pass with seed_1.",
                    },
                },
                "required": ["match_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_match_seeds",
            "description": (
                "Propose rewriting placeholder seeds on existing matches (requires Confirm). "
                "Use this when a bracket's default pairings should change — e.g. 1v8, 2v7, "
                "3v5, 4v6 instead of 1v8, 2v7, 3v6, 4v5. Later-round matches keep their "
                "seed slots (1v4, 2v3, …); only list the matches whose pairings change. "
                "Call list_matches first. A seed may appear only once in the same round."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "match_id": {"type": "integer"},
                                "seed_1": {"type": "integer"},
                                "seed_2": {"type": "integer"},
                            },
                            "required": ["match_id", "seed_1", "seed_2"],
                        },
                    }
                },
                "required": ["updates"],
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
            "name": "propose_match_score",
            "description": (
                "Propose recording a match result (requires Confirm). On Confirm this writes "
                "the score, completes the match, recomputes standings and current seeding, "
                "applies any bracket/cross-pool seed swap, and fills the next stage — so do "
                "NOT also propose generate_fixtures. A forfeit is entered as a score "
                "(15-0 to the team that showed up) with forfeit=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "match_id": {"type": "integer"},
                    "score_team_1": {"type": "integer"},
                    "score_team_2": {"type": "integer"},
                    "forfeit": {"type": "boolean"},
                },
                "required": ["match_id", "score_team_1", "score_team_2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_shift_schedule",
            "description": (
                "Propose moving matches by a fixed number of minutes — the weather-delay "
                "tool (requires Confirm). Completed matches are always excluded. Narrow the "
                "scope with from_time, day, field_id or match_ids; with no scope it moves "
                "every unplayed scheduled match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shift_mins": {"type": "integer"},
                    "from_time": {"type": "string"},
                    "day": {"type": "string"},
                    "field_id": {"type": "integer"},
                    "match_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["shift_mins"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete_stage",
            "description": (
                "Propose deleting a stage and all of its matches (requires Confirm). Refused "
                "if any of its matches is completed, if a bracket has already been seeded "
                "from it, or — for pools and Swiss groups — once the tournament is live. Use "
                "this to rebuild a stage that was created wrong."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "enum": ["pool", "swiss", "cross_pool", "bracket", "position_pool"],
                    },
                    "stage_id": {"type": "integer"},
                },
                "required": ["stage", "stage_id"],
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
            "description": (
                "Propose a full structure setup recipe (requires Confirm). pool_defs "
                "seeding must be snake draft. bracket_names like '1-4' include the "
                "3rd-place / push-in match automatically."
            ),
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
                "Run the deterministic scheduler and propose a bulk schedule (requires Confirm). "
                "Places pools/Swiss first, then cross-pool, then brackets — a semi never starts "
                "while a pool is still on. Default first pull is 07:00. Pass end_date for a "
                "multi-day event. After it returns, call check_schedule_conflicts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "duration_mins": {"type": "integer"},
                    "slot_buffer_mins": {
                        "type": "integer",
                        "description": "Gap between the end of one slot and the start of the "
                        "next, per field. Production norm is 15 (75-min games on 90-min slots).",
                    },
                    "min_rest_mins": {"type": "integer"},
                    "day_start_hour": {
                        "type": "integer",
                        "description": "First pull hour, wall-clock. Production default is 7.",
                    },
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
