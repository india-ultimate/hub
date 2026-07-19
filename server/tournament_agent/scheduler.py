"""Deterministic schedule recommender for unscheduled matches."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.utils import timezone

from server.tournament.models import Match, Tournament, TournamentField


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def recommend_schedule(
    *,
    tournament: Tournament,
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
    start = _parse_date(start_date)
    end = _parse_date(end_date) if end_date else start

    fields_qs = TournamentField.objects.filter(tournament=tournament)
    if field_ids:
        fields_qs = fields_qs.filter(id__in=field_ids)
    fields = list(fields_qs.order_by("name"))
    if not fields:
        return {"assignments": [], "notes": "No fields available", "meta": {}}

    matches = list(
        Match.objects.filter(tournament=tournament, time__isnull=True)
        .select_related("team_1", "team_2")
        .order_by("id")
    )
    if not matches:
        matches = list(
            Match.objects.filter(tournament=tournament, field__isnull=True)
            .select_related("team_1", "team_2")
            .order_by("id")
        )

    # Occupancy: (field_id, datetime) slots already taken
    occupied: set[tuple[int, datetime]] = set()
    for m in Match.objects.filter(tournament=tournament, time__isnull=False, field__isnull=False):
        if m.field_id is None or m.time is None:
            continue
        naive = m.time.replace(tzinfo=None) if m.time.tzinfo else m.time
        occupied.add((m.field_id, naive))

    team_last_end: dict[int, datetime] = {}
    assignments: list[dict[str, Any]] = []
    unplaced = 0

    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    slot_length = timedelta(minutes=duration_mins)
    rest = timedelta(minutes=min_rest_mins)

    def candidate_slots(day: date) -> list[datetime]:
        slots: list[datetime] = []
        cursor = datetime(day.year, day.month, day.day, day_start_hour, 0, 0)
        day_end = datetime(day.year, day.month, day.day, day_end_hour, 0, 0)
        lunch_start = (
            datetime(day.year, day.month, day.day, lunch_start_hour, 0, 0)
            if lunch_start_hour is not None
            else None
        )
        lunch_end = (
            datetime(day.year, day.month, day.day, lunch_end_hour, 0, 0)
            if lunch_end_hour is not None
            else None
        )
        while cursor + slot_length <= day_end:
            slot_end = cursor + slot_length
            if lunch_start and lunch_end and not (slot_end <= lunch_start or cursor >= lunch_end):
                cursor = lunch_end
                continue
            slots.append(cursor)
            cursor += slot_length
        return slots

    for match in matches:
        placed = False
        team_ids = [tid for tid in (match.team_1_id, match.team_2_id) if tid]
        for day in days:
            for slot in candidate_slots(day):
                # Rest check
                ok_rest = True
                for tid in team_ids:
                    last = team_last_end.get(tid)
                    if last and slot < last + rest:
                        ok_rest = False
                        break
                if not ok_rest:
                    continue
                for field in fields:
                    key = (field.id, slot)
                    if key in occupied:
                        continue
                    occupied.add(key)
                    end_t = slot + slot_length
                    for tid in team_ids:
                        prev = team_last_end.get(tid)
                        if prev is None or end_t > prev:
                            team_last_end[tid] = end_t
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
            "min_rest_mins": min_rest_mins,
            "fields_used": [f.id for f in fields],
            "unplaced": unplaced,
        },
    }
