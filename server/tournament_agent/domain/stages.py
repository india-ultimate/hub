"""The stage kinds a tournament is built from.

This is the one list in the package: the tool schemas advertise it, the reads
bucket matches by it, the snapshot tallies by it, and `services.proposals` applies
against it — so the kinds the model may name and the kinds that can be applied
cannot drift apart.

It lives in `domain` rather than beside the read tools because everything above
needs it and it depends on nothing but the tournament models. `tools.queries`
re-exports both names, so callers there are unaffected.
"""

from __future__ import annotations

from typing import Any

from server.tournament.models import (
    Bracket,
    CrossPool,
    Pool,
    PositionPool,
    SwissRound,
)

# Stage kind -> the Match FK naming it.
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
