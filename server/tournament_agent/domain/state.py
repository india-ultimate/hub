"""One read of the tournament, rendered for the model.

The model is not asked to remember what it built. Every turn pins the block this
module renders, so "did the pools get created?" is answered by the database
rather than by whatever the assistant said last turn. Chat history is a record of
what staff asked for; this is a record of what exists.

`build_snapshot` is the only place the turn queries stage/match state, so an
action's inputs are one object rather than ambient queries scattered through the
loop.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from server.tournament.models import Match, Tournament, TournamentField
from server.tournament_agent.domain.stages import STAGE_FIELDS, STAGE_MODELS
from server.tournament_agent.models import (
    AgentProposal,
    ProposalStatus,
    TournamentAgentSession,
)

# Enough for staff to see the shape of the event without pasting the whole grid.
MAX_LISTED_FIELDS = 12
MAX_LISTED_STAGES = 16
MAX_LISTED_PROPOSALS = 10
SUMMARY_CHARS = 110
ERROR_CHARS = 160


@dataclass(frozen=True)
class StageRow:
    stage: str
    id: int
    name: str
    sequence_number: int
    seeds: list[int]
    match_count: int
    completed_count: int
    unscheduled_count: int


@dataclass(frozen=True)
class ProposalRow:
    id: int
    tool_name: str
    summary: str
    last_error: str = ""


@dataclass(frozen=True)
class TournamentSnapshot:
    """Everything the turn needs to know about the tournament, read once."""

    tournament_id: int
    title: str
    status: str
    start_date: str
    end_date: str
    team_count: int
    field_names: list[str] = field(default_factory=list)
    stages: list[StageRow] = field(default_factory=list)
    match_count: int = 0
    scheduled_count: int = 0
    completed_count: int = 0
    pending: list[ProposalRow] = field(default_factory=list)
    applied: list[ProposalRow] = field(default_factory=list)

    @property
    def unscheduled_count(self) -> int:
        return self.match_count - self.scheduled_count

    @property
    def has_fields(self) -> bool:
        return bool(self.field_names)

    @property
    def has_stages(self) -> bool:
        return bool(self.stages)


def _seed_list(row: Any) -> list[int]:
    """Seeds a stage was built from, low to high. Brackets carry theirs in the name."""
    seeding = getattr(row, "initial_seeding", None) or {}
    if isinstance(seeding, dict):
        values: list[Any] = list(seeding.keys())
    elif isinstance(seeding, list):
        values = list(seeding)
    else:
        return []
    seeds = []
    for value in values:
        try:
            seeds.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(seeds)


def build_snapshot(session: TournamentAgentSession) -> TournamentSnapshot:
    tournament: Tournament = session.tournament
    event = tournament.event

    # One grouped pass over matches, the same shape `list_stages` uses: four
    # aggregates plus a row fetch per stage is what this replaces.
    tallies: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "completed": 0, "unscheduled": 0}
    )
    match_count = scheduled_count = completed_count = 0
    for row in Match.objects.filter(tournament=tournament).values(
        "status", "time", "field_id", *(f"{name}_id" for name in STAGE_FIELDS.values())
    ):
        match_count += 1
        is_scheduled = row["time"] is not None and row["field_id"] is not None
        is_done = row["status"] == Match.Status.COMPLETED
        if is_scheduled:
            scheduled_count += 1
        if is_done:
            completed_count += 1
        stage = next((s for s, name in STAGE_FIELDS.items() if row[f"{name}_id"]), None)
        if stage is None:
            continue
        tally = tallies[(stage, row[f"{STAGE_FIELDS[stage]}_id"])]
        tally["total"] += 1
        if is_done:
            tally["completed"] += 1
        if not is_scheduled:
            tally["unscheduled"] += 1

    empty = {"total": 0, "completed": 0, "unscheduled": 0}
    stages: list[StageRow] = []
    for stage, model in STAGE_MODELS.items():
        rows = model.objects.filter(tournament=tournament)
        if stage != "cross_pool":
            rows = rows.order_by("sequence_number")
        for row in rows:
            tally = tallies.get((stage, row.id), empty)
            stages.append(
                StageRow(
                    stage=stage,
                    id=row.id,
                    name=str(getattr(row, "name", "") or "Cross Pool"),
                    sequence_number=int(getattr(row, "sequence_number", 1) or 1),
                    seeds=_seed_list(row),
                    match_count=tally["total"],
                    completed_count=tally["completed"],
                    unscheduled_count=tally["unscheduled"],
                )
            )

    proposals = session.proposals.filter(
        status__in=(ProposalStatus.PENDING, ProposalStatus.CONFIRMED)
    ).order_by("created_at")
    pending: list[ProposalRow] = []
    applied: list[ProposalRow] = []
    for row in proposals:
        bucket = pending if row.status == ProposalStatus.PENDING else applied
        bucket.append(
            ProposalRow(
                id=row.id,
                tool_name=row.tool_name,
                summary=row.summary or "",
                last_error=row.last_error or "",
            )
        )

    return TournamentSnapshot(
        tournament_id=tournament.id,
        title=event.title,
        status=tournament.status,
        start_date=str(event.start_date),
        end_date=str(event.end_date),
        team_count=tournament.teams.count(),
        field_names=[
            f.name
            for f in TournamentField.objects.filter(tournament=tournament).order_by("name")[
                :MAX_LISTED_FIELDS
            ]
        ],
        stages=stages,
        match_count=match_count,
        scheduled_count=scheduled_count,
        completed_count=completed_count,
        pending=pending,
        applied=applied,
    )


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _stage_line(row: StageRow) -> str:
    parts = [f"{row.stage} {row.name} (#{row.id})"]
    if row.seeds:
        parts.append(f"seeds {row.seeds}")
    parts.append(f"{row.match_count} matches")
    if row.completed_count:
        parts.append(f"{row.completed_count} played")
    if row.unscheduled_count:
        parts.append(f"{row.unscheduled_count} unscheduled")
    return ", ".join(parts)


def render_state(snapshot: TournamentSnapshot, phase_line: str = "") -> str:
    """The block pinned to every turn. Kept terse — it is resent on every round."""
    lines = [
        "## Tournament state (read from the database at the start of this turn)",
        "This is what exists. Where it disagrees with something you said earlier, this "
        "wins. It does not override what staff are asking you for now — if they name a "
        "date, a duration or a count, use theirs.",
        f"{snapshot.title} · status {snapshot.status} · {snapshot.team_count} teams",
    ]
    if phase_line:
        lines.append(phase_line)

    if snapshot.field_names:
        lines.append(f"Fields ({len(snapshot.field_names)}): {', '.join(snapshot.field_names)}")
    else:
        lines.append("Fields: none yet.")

    if snapshot.stages:
        lines.append(f"Stages ({len(snapshot.stages)}):")
        lines.extend(f"- {_stage_line(row)}" for row in snapshot.stages[:MAX_LISTED_STAGES])
        if len(snapshot.stages) > MAX_LISTED_STAGES:
            lines.append(f"- …and {len(snapshot.stages) - MAX_LISTED_STAGES} more")
    else:
        lines.append("Stages: none yet.")

    lines.append(
        f"Matches: {snapshot.match_count} total, {snapshot.scheduled_count} scheduled, "
        f"{snapshot.completed_count} completed"
    )

    if snapshot.pending:
        lines.append("Pending proposals — staff Confirm these on the card, never in chat:")
        for row in snapshot.pending[:MAX_LISTED_PROPOSALS]:
            lines.append(f"- #{row.id} {row.tool_name}: {_clip(row.summary, SUMMARY_CHARS)}")
            if row.last_error:
                lines.append(
                    f"  APPLY FAILED: {_clip(row.last_error, ERROR_CHARS)} "
                    "— re-propose with a corrected payload, do not reuse this one."
                )
    else:
        lines.append("Pending proposals: none.")

    if snapshot.applied:
        shown = snapshot.applied[-MAX_LISTED_PROPOSALS:]
        lines.append("Applied this session (these are done and live):")
        lines.extend(
            f"- #{row.id} {row.tool_name}: {_clip(row.summary, SUMMARY_CHARS)}" for row in shown
        )
    else:
        lines.append("Applied this session: nothing yet.")

    lines.append(
        "Anything you planned that is not listed above has not happened. Do not tell "
        "staff it exists."
    )
    return "\n".join(lines)
