"""The one move staff should make next, when there is only one.

Confirming a proposal leaves the conversation empty: the plan is applied, the
card is gone, and the box is blank. Staff who do not run tournaments for a living
have no way to know whether the event now needs a bracket, a schedule, or
nothing at all.

The phase already answers that — it is the same derivation the tool gate uses, so
a suggestion here can never point at something the agent would then refuse. That
matters more than it sounds: the rail used to compute its own version of setup
order in JavaScript and could suggest a format on a tournament with no fields,
which the gate declines.

Deliberately silent unless the answer is certain. A suggestion that appears on
every turn is noise staff learn to ignore, and the point is to be trusted on the
turn it does appear.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.tournament_agent.domain.phase import Phase
from server.tournament_agent.domain.state import TournamentSnapshot

# Stages that decide final placings. A tournament with groups but none of these
# has nothing to play for after the pools finish.
FINALS_STAGES = frozenset({"bracket", "position_pool"})
GROUP_STAGES = frozenset({"pool", "swiss"})


@dataclass(frozen=True)
class NextStep:
    label: str
    prompt: str
    why: str


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular}" if count == 1 else f"{count} {plural}"


def next_step_for(snapshot: TournamentSnapshot, phase: Phase) -> NextStep | None:
    """The next move, or None when it is not obvious enough to put in front of staff."""
    # Something is already asking for their attention. Two calls to action at once
    # is worse than none.
    if snapshot.pending:
        return None
    # Teams arrive through registration; the agent cannot add them, so pointing at
    # a next step here would be a dead end.
    if snapshot.team_count == 0:
        return None

    if phase is Phase.NO_FIELDS:
        return NextStep(
            label="Add fields",
            prompt="Add the playing fields for this tournament",
            why="Nothing can be built or scheduled until the event has somewhere to play.",
        )

    if phase is Phase.NO_STAGES:
        return NextStep(
            label="Choose a format",
            prompt="Recommend a format for the registered teams",
            why="The format decides every match, so it comes before any schedule.",
        )

    stages = {row.stage for row in snapshot.stages}
    has_groups = bool(stages & GROUP_STAGES)
    has_finals = bool(stages & FINALS_STAGES)

    # `propose_create_cross_pool` makes the stage and no matches, so a cross pool
    # can sit there empty with nothing pointing at it.
    empty_cross = [
        row for row in snapshot.stages if row.stage == "cross_pool" and row.match_count == 0
    ]
    if empty_cross and phase in (Phase.NO_SCHEDULE, Phase.READY):
        return NextStep(
            label="Add cross-pool matches",
            prompt="Create the cross-pool matches",
            why="The cross-pool stage exists but has no matches in it yet.",
        )

    # Groups with nowhere to go. Suggesting a start here is worse than saying
    # nothing: it invites staff to lock in an event that cannot produce placings,
    # and starting is not something they can quietly undo.
    if has_groups and not has_finals and phase in (Phase.NO_SCHEDULE, Phase.READY):
        return NextStep(
            label="Add the finals",
            prompt="Add the bracket and any cross-pool stage this format needs",
            why="Pools decide seeding, but nothing decides the final placings yet.",
        )

    if phase in (Phase.NO_SCHEDULE, Phase.LIVE) and snapshot.unscheduled_count > 0:
        return NextStep(
            label=f"Schedule {_plural(snapshot.unscheduled_count, 'match', 'matches')}",
            prompt="Recommend a schedule for the matches that are not scheduled yet",
            why="Every match still needs a time and a field.",
        )

    if phase is Phase.READY:
        return NextStep(
            label="Start the tournament",
            prompt="Start the tournament",
            why="Every match has a time and a field, so teams can be assigned.",
        )

    return None


# What the composer invites staff to type. Hardcoded, it advertised pools and
# schedules to someone standing on a field trying to enter a score.
PLACEHOLDERS: dict[Phase, str] = {
    Phase.NO_FIELDS: "Ask to add fields, or how to set this tournament up…",
    Phase.NO_STAGES: "Ask for pools, Swiss groups, or a bracket…",
    Phase.NO_SCHEDULE: "Ask for a schedule, or add another stage…",
    Phase.READY: "Ask to start the tournament, or change the schedule…",
    Phase.LIVE: "Enter a score, move a match, or check the standings…",
    Phase.COMPLETE: "Ask about final standings, spirit scores, or results…",
}


def placeholder_for(phase: Phase) -> str:
    return PLACEHOLDERS[phase]
