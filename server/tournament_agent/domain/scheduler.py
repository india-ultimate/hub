"""Deterministic schedule recommender for unscheduled matches."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Q
from django.utils import timezone

from server.tournament.models import Match, Tournament, TournamentField
from server.tournament_agent.domain.validate import seed_to_team, side_keys

# Matches are placed in this order so a stage never lands before the stage that
# feeds it. Within a stage, creation order (id) is kept.
STAGE_ORDER = {"pool": 0, "swiss_round": 0, "cross_pool": 1, "bracket": 2, "position_pool": 2}


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _stage_rank(match: Match) -> int:
    if match.pool_id or match.swiss_round_id:
        return STAGE_ORDER["pool"]
    if match.cross_pool_id:
        return STAGE_ORDER["cross_pool"]
    return STAGE_ORDER["bracket"]


def _rest_keys(match: Match, seeding: dict[int, int]) -> list[str]:
    """Identify the two sides of a match for rest checks.

    Teams are only attached once the tournament starts, but pools are normally
    created and scheduled before that. `side_keys` resolves a placeholder seed back
    to its team, so rest is enforced across a part-way-live tournament where one
    team holds a team id on its pool match and only a seed on its bracket match.
    """
    return [key for key, _team_id, _label in side_keys(match, seeding)]


def recommend_schedule(
    *,
    tournament: Tournament,
    start_date: str,
    end_date: str | None = None,
    duration_mins: int = 75,
    slot_buffer_mins: int = 15,
    min_rest_mins: int = 60,
    day_start_hour: int = 9,
    day_end_hour: int = 18,
    lunch_start_hour: int | None = 13,
    lunch_end_hour: int | None = 14,
    field_ids: list[int] | None = None,
) -> dict[str, Any]:
    start = _parse_date(start_date)
    end = _parse_date(end_date) if end_date else start

    fields_qs = TournamentField.objects.filter(tournament=tournament)
    if field_ids:
        fields_qs = fields_qs.filter(id__in=field_ids)
    fields = list(fields_qs.order_by("name"))
    if not fields:
        return {"assignments": [], "notes": "No fields available", "meta": {}}

    # "Unscheduled" means missing a time or a field — the same definition the
    # overview counts by. Completed matches are never moved.
    matches = sorted(
        Match.objects.filter(tournament=tournament)
        .filter(Q(time__isnull=True) | Q(field__isnull=True))
        .exclude(status=Match.Status.COMPLETED)
        .select_related("team_1", "team_2"),
        key=lambda m: (_stage_rank(m), m.id),
    )

    # Occupancy: (field_id, datetime) slots already taken
    occupied: set[tuple[int, datetime]] = set()
    for m in Match.objects.filter(tournament=tournament, time__isnull=False, field__isnull=False):
        if m.field_id is None or m.time is None:
            continue
        naive = m.time.replace(tzinfo=None) if m.time.tzinfo else m.time
        occupied.add((m.field_id, naive))

    seeding = seed_to_team(tournament)
    last_end: dict[str, datetime] = {}
    assignments: list[dict[str, Any]] = []
    unplaced = 0

    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    slot_length = timedelta(minutes=duration_mins)
    slot_step = timedelta(minutes=duration_mins + max(0, slot_buffer_mins))
    rest = timedelta(minutes=min_rest_mins)

    def candidate_slots(day: date) -> list[datetime]:
        # Naive on purpose: slots are a wall-clock grid for the day, and each one
        # is made aware in the tournament's timezone only when it is assigned.
        slots: list[datetime] = []
        cursor = datetime(day.year, day.month, day.day, day_start_hour, 0, 0)  # noqa: DTZ001
        day_end = datetime(day.year, day.month, day.day, day_end_hour, 0, 0)  # noqa: DTZ001
        lunch_start = (
            datetime(day.year, day.month, day.day, lunch_start_hour, 0, 0)  # noqa: DTZ001
            if lunch_start_hour is not None
            else None
        )
        lunch_end = (
            datetime(day.year, day.month, day.day, lunch_end_hour, 0, 0)  # noqa: DTZ001
            if lunch_end_hour is not None
            else None
        )
        while cursor + slot_length <= day_end:
            slot_end = cursor + slot_length
            if lunch_start and lunch_end and not (slot_end <= lunch_start or cursor >= lunch_end):
                cursor = lunch_end
                continue
            slots.append(cursor)
            cursor += slot_step
        return slots

    slots_by_day = {day: candidate_slots(day) for day in days}

    for match in matches:
        placed = False
        keys = _rest_keys(match, seeding)
        for day in days:
            for slot in slots_by_day[day]:
                if any(slot < last_end[key] + rest for key in keys if key in last_end):
                    continue
                for field in fields:
                    if (field.id, slot) in occupied:
                        continue
                    occupied.add((field.id, slot))
                    slot_end = slot + slot_length
                    for key in keys:
                        last_end[key] = max(slot_end, last_end.get(key, slot_end))
                    aware = timezone.make_aware(slot) if timezone.is_naive(slot) else slot
                    assignments.append(
                        {
                            "match_id": match.id,
                            "time": aware.isoformat(),
                            "field_id": field.id,
                            "duration_mins": duration_mins,
                        }
                    )
                    placed = True
                    break
                if placed:
                    break
            if placed:
                break
        if not placed:
            unplaced += 1

    notes = f"Placed {len(assignments)} matches"
    if unplaced:
        notes += f"; {unplaced} could not be placed with current constraints"
    return {
        "assignments": assignments,
        "notes": notes,
        "meta": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "duration_mins": duration_mins,
            "slot_buffer_mins": slot_buffer_mins,
            "min_rest_mins": min_rest_mins,
            "fields_used": [f.id for f in fields],
            "unplaced": unplaced,
        },
    }
