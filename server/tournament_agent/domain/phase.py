"""Where a tournament is in its life, derived from the database.

Setup has an order — fields, then stages, then a schedule, then start — and until
now that order lived in the prompt as a numbered rule the model could ignore. It
is a state machine, so it belongs here: `phase_for` says where the tournament is,
and `policy` decides which tools that phase may use.

Phases are computed, never stored. There is no transition to fire and nothing to
keep in sync — a confirmed proposal changes the database, and the next turn's
snapshot lands in whichever phase that produced.
"""

from __future__ import annotations

from enum import Enum

from server.tournament.models import Tournament
from server.tournament_agent.domain.state import TournamentSnapshot


class Phase(str, Enum):
    NO_FIELDS = "no_fields"
    NO_STAGES = "no_stages"
    NO_SCHEDULE = "no_schedule"
    READY = "ready"
    LIVE = "live"
    COMPLETE = "complete"


# What the phase means and what staff can do next, for the state block. Kept to one
# line each: this text ships on every round.
PHASE_GUIDANCE: dict[Phase, str] = {
    Phase.NO_FIELDS: (
        "no fields exist yet. Fields come first — ask how many if staff have not said, "
        "then propose them and stop. Stages and schedules are not available yet."
    ),
    Phase.NO_STAGES: (
        "fields exist, no stages yet. Propose the format (pools / Swiss / bracket) and "
        "stop. There are no matches to schedule until a stage is confirmed."
    ),
    Phase.NO_SCHEDULE: (
        "stages exist with matches still unplaced. Propose one schedule, then call "
        "check_schedule_conflicts. Never stack two overlapping grids."
    ),
    Phase.READY: (
        "every match has a time and a field. The tournament can be started once staff "
        "are happy with the grid."
    ),
    Phase.LIVE: (
        "the tournament is running. Enter scores, progress stages, and repair the "
        "schedule match by match — never re-run the whole scheduler."
    ),
    Phase.COMPLETE: "the tournament is finished. Reads only — nothing here can be changed.",
}


def phase_for(snapshot: TournamentSnapshot) -> Phase:
    if snapshot.status == Tournament.Status.COMPLETED:
        return Phase.COMPLETE
    if snapshot.status == Tournament.Status.LIVE:
        return Phase.LIVE
    if not snapshot.has_fields:
        return Phase.NO_FIELDS
    if not snapshot.has_stages:
        return Phase.NO_STAGES
    # A stage whose fixtures were never generated has nothing to place yet, so it
    # is not "ready" — it belongs with the other unfinished schedules.
    if snapshot.match_count == 0 or snapshot.unscheduled_count > 0:
        return Phase.NO_SCHEDULE
    return Phase.READY


def phase_line(phase: Phase) -> str:
    return f"Phase {phase.value.upper()} — {PHASE_GUIDANCE[phase]}"
