"""Stage maps and match-row shaping, shared by the read tools and the proposal tools.

`STAGE_FIELDS` is the one list of stage kinds in the package: the tool schemas
advertise it, the reads bucket matches by it, and `services.proposals` applies
against it, so the kinds the model may name and the kinds that can be applied
cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    Pool,
    PositionPool,
    SwissRound,
    Tournament,
)

# Stage kind -> the Match FK naming it, and the model behind it.
STAGE_FIELDS = {
    "pool": "pool",
    "swiss": "swiss_round",
    "cross_pool": "cross_pool",
    "bracket": "bracket",
    "position_pool": "position_pool",
}

STAGE_MODELS: dict[str, Any] = {
    "pool": Pool,
    "swiss": SwissRound,
    "cross_pool": CrossPool,
    "bracket": Bracket,
    "position_pool": PositionPool,
}


def _match_stage(m: Match) -> str | None:
    for stage, attr in STAGE_FIELDS.items():
        if getattr(m, f"{attr}_id"):
            return stage
    return None


def _match_row(m: Match) -> dict[str, Any]:
    stage = _match_stage(m)
    stage_obj = getattr(m, STAGE_FIELDS[stage]) if stage else None
    return {
        "id": m.id,
        "name": m.name,
        "status": m.status,
        "stage": stage,
        # Round number within the stage: bracket QF/SF/final, cross pool round 1 vs 2.
        "sequence_number": m.sequence_number,
        "stage_name": getattr(stage_obj, "name", "Cross Pool") if stage_obj else None,
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
    }


def match_queryset(tournament: Tournament) -> Any:
    return Match.objects.filter(tournament=tournament).select_related(
        "field", "team_1", "team_2", "pool", "bracket", "swiss_round", "position_pool", "cross_pool"
    )
