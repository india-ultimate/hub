"""Computed schedule checks, so the agent verifies instead of eyeballing a grid."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

from server.tournament.models import Match, Tournament

# A stage may not start before every stage that feeds it has finished.
STAGE_RANK = {"pool": 0, "swiss_round": 0, "cross_pool": 1, "bracket": 2, "position_pool": 2}

HEALTHY_MATCHES_PER_FIELD_PER_DAY = 9
MAX_MATCHES_PER_TEAM_PER_DAY = 4
# Mirrors Match.duration_mins' default, for rows that somehow carry 0 or None.
DEFAULT_MATCH_MINS = 75


def _rank(match: Match) -> int:
    if match.pool_id or match.swiss_round_id:
        return STAGE_RANK["pool"]
    if match.cross_pool_id:
        return STAGE_RANK["cross_pool"]
    return STAGE_RANK["bracket"]


def _label(match: Match) -> str:
    return match.name or f"match {match.id}"


def seed_to_team(tournament: Tournament) -> dict[int, int]:
    """seed -> team_id, preferring the seeding upsets have already rewritten.

    `populate_fixtures` fills bracket and cross-pool placeholders from
    `current_seeding`, so that is the map that says who a seed will actually be.
    """
    seeding = tournament.current_seeding or tournament.initial_seeding or {}
    resolved: dict[int, int] = {}
    for seed, team_id in seeding.items():
        try:
            resolved[int(seed)] = int(team_id)
        except (TypeError, ValueError):
            continue  # a bracket seeded with 0 / null is not filled yet
    return {seed: team_id for seed, team_id in resolved.items() if team_id > 0}


def side_keys(
    match: Match, seeding: dict[int, int], names: dict[int, str] | None = None
) -> list[tuple[str, int | None, str]]:
    """(key, team_id, label) for each side of a match.

    A seed resolves to its team so one team is never tracked under two keys. Without
    that, a part-way-live tournament registers a team's pool match under `t42` and
    checks its bracket match under `s5`: rest between them goes unenforced and the
    team's daily match count is split across two labels.
    """
    sides: list[tuple[str, int | None, str]] = []
    for team_id, team, seed in (
        (match.team_1_id, match.team_1, match.placeholder_seed_1),
        (match.team_2_id, match.team_2, match.placeholder_seed_2),
    ):
        if team_id:
            label = (names or {}).get(team_id) or (team.name if team else "") or f"team {team_id}"
            sides.append((f"t{team_id}", team_id, label))
            continue
        if not seed:
            continue
        seeded_team = seeding.get(int(seed))
        if seeded_team is None:
            # No team behind this seed yet — the seed is the best identity available.
            sides.append((f"s{seed}", None, f"seed {seed}"))
            continue
        label = (names or {}).get(seeded_team) or f"seed {seed}"
        sides.append((f"t{seeded_team}", seeded_team, label))
    return sides


def schedule_conflicts(
    tournament: Tournament,
    *,
    min_rest_mins: int = 60,
    day_end_hour: int = 18,
    day: str | None = None,
) -> dict[str, Any]:
    matches = list(
        Match.objects.filter(tournament=tournament).select_related("field", "team_1", "team_2")
    )
    # Resolve each placed match to its window once, up front. Everything below works
    # from `start`/`end` rather than re-deriving them from `Match.time`, which is
    # nullable and would otherwise need narrowing at every use.
    scheduled: list[tuple[Match, datetime, datetime]] = []
    for m in matches:
        if m.time is None or m.field_id is None:
            continue
        if day and m.time.date().isoformat() != day:
            continue
        scheduled.append(
            (m, m.time, m.time + timedelta(minutes=m.duration_mins or DEFAULT_MATCH_MINS))
        )
    scheduled.sort(key=lambda row: (row[1], row[0].id))

    seeding = seed_to_team(tournament)
    per_field_day: dict[tuple[str, str], int] = defaultdict(int)
    # Keyed by the stable side key, not the display label, so a team counted once
    # under its name and once under a seed cannot slip past the per-day cap.
    per_side_day: dict[tuple[str, str], int] = defaultdict(int)
    side_labels: dict[str, str] = {}
    # Consecutive-pair scanning over a sorted timeline, once per field and once
    # per team/seed. `unique_together` already blocks two matches sharing an exact
    # (field, time), so what actually goes wrong is an *overlap*.
    field_windows: dict[str, list[tuple[datetime, datetime, Match, str]]] = defaultdict(list)
    side_windows: dict[str, list[tuple[datetime, datetime, Match, str]]] = defaultdict(list)

    for m, start, end in scheduled:
        day_key = start.date().isoformat()
        field_name = m.field.name if m.field else str(m.field_id)
        per_field_day[(field_name, day_key)] += 1
        field_windows[field_name].append((start, end, m, field_name))
        for key, _team_id, label in side_keys(m, seeding):
            per_side_day[(key, day_key)] += 1
            # A team named on one match and seeded on another: prefer the real name.
            if label and not side_labels.get(key, "").strip():
                side_labels[key] = label
            side_windows[key].append((start, end, m, label))

    # Sorted once, here, so the rest scan below does not depend on `overlaps` having
    # sorted these lists as a side effect of running first.
    for windows in (field_windows, side_windows):
        for entries in windows.values():
            entries.sort(key=lambda w: (w[0], w[2].id))

    def overlaps(
        windows: dict[str, list[tuple[datetime, datetime, Match, str]]]
    ) -> list[dict[str, Any]]:
        found = []
        for entries in windows.values():
            for (start_a, end_a, match_a, label), (start_b, _e, match_b, _l) in pairwise(entries):
                if start_b < end_a:
                    found.append(
                        {
                            "subject": label,
                            "matches": [_label(match_a), _label(match_b)],
                            "times": [start_a.isoformat(), start_b.isoformat()],
                        }
                    )
        return found

    field_overlaps = overlaps(field_windows)
    team_overlaps = overlaps(side_windows)

    rest_violations: list[dict[str, Any]] = []
    for entries in side_windows.values():
        for (_start_a, end_a, match_a, label), (start_b, _e, match_b, _l) in pairwise(entries):
            if start_b < end_a:
                continue  # already reported as an overlap
            gap = int((start_b - end_a).total_seconds() // 60)
            if gap < min_rest_mins:
                rest_violations.append(
                    {
                        "team": label,
                        "gap_mins": gap,
                        "required_mins": min_rest_mins,
                        "matches": [_label(match_a), _label(match_b)],
                    }
                )

    latest_end_by_rank: dict[int, datetime] = {}
    for m, _start, end in scheduled:
        rank = _rank(m)
        latest_end_by_rank[rank] = max(latest_end_by_rank.get(rank, end), end)

    stage_order_violations = [
        {
            "match": _label(m),
            "time": start.isoformat(),
            "blocked_until": latest_end_by_rank[earlier].isoformat(),
        }
        for m, start, _end in scheduled
        for earlier in range(_rank(m))
        if earlier in latest_end_by_rank and start < latest_end_by_rank[earlier]
    ]

    def _ends_late(end: datetime) -> bool:
        return end > end.replace(hour=day_end_hour, minute=0, second=0, microsecond=0)

    outside_window = [
        {"match": _label(m), "ends": end.isoformat()}
        for m, _start, end in scheduled
        if _ends_late(end)
    ]

    unscheduled = [m for m in matches if not (m.time and m.field_id)]
    problems = (
        len(field_overlaps)
        + len(team_overlaps)
        + len(rest_violations)
        + len(stage_order_violations)
    )
    return {
        "ok": problems == 0,
        "problem_count": problems,
        "field_overlaps": field_overlaps,
        "team_overlaps": team_overlaps,
        "rest_violations": rest_violations,
        "stage_order_violations": stage_order_violations,
        "outside_day_window": outside_window,
        "unscheduled_matches": [_label(m) for m in unscheduled],
        "matches_per_field_per_day": [
            {
                "field": field,
                "day": day_key,
                "count": count,
                "overpacked": count > HEALTHY_MATCHES_PER_FIELD_PER_DAY,
            }
            for (field, day_key), count in sorted(per_field_day.items())
        ],
        "matches_per_team_per_day": [
            {
                "team": side_labels.get(key, key),
                "day": day_key,
                "count": count,
                "too_many": count > MAX_MATCHES_PER_TEAM_PER_DAY,
            }
            for (key, day_key), count in sorted(per_side_day.items())
        ],
    }
