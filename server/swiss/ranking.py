import secrets
from collections.abc import Iterable, Mapping, Sequence
from itertools import groupby

SwissGame = tuple[int, int, int, int]


def points(row: Mapping[str, int]) -> int:
    return row.get("wins", 0) * 2 + row.get("draws", 0)


def opponent_strength(
    results: Mapping[int, Mapping[str, int]], games: Sequence[SwissGame]
) -> dict[int, int]:
    strength = dict.fromkeys(results, 0)
    for t1, t2, _, _ in games:
        strength[t1] += points(results[t2])
        strength[t2] += points(results[t1])
    return strength


def draw_lots(team_ids: Iterable[int]) -> dict[int, int]:
    ids = list(team_ids)
    numbers = list(range(1, len(ids) + 1))
    secrets.SystemRandom().shuffle(numbers)
    return dict(zip(ids, numbers, strict=True))


def _head_to_head_wins(group: set[int], games: Sequence[SwissGame]) -> dict[int, int]:
    wins = dict.fromkeys(group, 0)
    for t1, t2, s1, s2 in games:
        if t1 in group and t2 in group:
            if s1 > s2:
                wins[t1] += 1
            elif s2 > s1:
                wins[t2] += 1
    return wins


def _break_tie(
    group: list[int],
    results: Mapping[int, Mapping[str, int]],
    games: Sequence[SwissGame],
    strength: Mapping[int, int],
    lots: Mapping[int, int],
) -> list[int]:
    if len(group) == 1:
        return group
    h2h = _head_to_head_wins(set(group), games)
    criteria = {
        tid: (
            h2h[tid],
            strength[tid],
            results[tid].get("GF", 0) - results[tid].get("GA", 0),
            results[tid].get("GF", 0),
        )
        for tid in group
    }
    for index in range(4):
        if len({criteria[tid][index] for tid in group}) > 1:
            ordered = sorted(group, key=lambda tid: criteria[tid][index], reverse=True)
            out: list[int] = []
            for _, sub in groupby(ordered, key=lambda tid: criteria[tid][index]):
                out += _break_tie(list(sub), results, games, strength, lots)
            return out
    return sorted(group, key=lambda tid: lots[tid] if lots else tid)


def rank_teams(
    results: Mapping[int, Mapping[str, int]],
    games: Sequence[SwissGame],
    lots: Mapping[int, int],
) -> list[int]:
    strength = opponent_strength(results, games)
    by_points = sorted(results, key=lambda tid: (-points(results[tid]), tid))
    ranked: list[int] = []
    for _, group in groupby(by_points, key=lambda tid: points(results[tid])):
        ranked += _break_tie(list(group), results, games, strength, lots)
    return ranked
