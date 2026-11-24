import secrets
from collections.abc import Iterable, Sequence


def _backtrack_pair(
    team_ids: Sequence[int],
    played: set[frozenset[int]],
    paired: set[int],
    pairs: list[tuple[int, int]],
    index: int,
) -> bool:
    while index < len(team_ids) and team_ids[index] in paired:
        index += 1
    if index >= len(team_ids):
        return True

    tid = team_ids[index]
    for j in range(index + 1, len(team_ids)):
        candidate = team_ids[j]
        if candidate in paired or frozenset([tid, candidate]) in played:
            continue
        paired.update((tid, candidate))
        pairs.append((tid, candidate))
        if _backtrack_pair(team_ids, played, paired, pairs, index + 1):
            return True
        paired.discard(tid)
        paired.discard(candidate)
        pairs.pop()
    return False


def pair_teams(order: Sequence[int], played: set[frozenset[int]]) -> list[tuple[int, int]]:
    paired: set[int] = set()
    pairs: list[tuple[int, int]] = []
    if _backtrack_pair(order, played, paired, pairs, 0):
        return pairs

    paired.clear()
    pairs.clear()
    for i, tid in enumerate(order):
        if tid in paired:
            continue
        unpaired = [c for c in order[i + 1 :] if c not in paired]
        fresh = [c for c in unpaired if frozenset([tid, c]) not in played]
        if choice := (fresh or unpaired):
            pairs.append((tid, choice[0]))
            paired.update((tid, choice[0]))
    return pairs


def select_bye(order: Sequence[int], had_bye: set[int]) -> int:
    for tid in reversed(order):
        if tid not in had_bye:
            return tid
    return order[-1]


def draw_order(team_ids: Iterable[int]) -> list[int]:
    order = list(team_ids)
    secrets.SystemRandom().shuffle(order)
    return order
