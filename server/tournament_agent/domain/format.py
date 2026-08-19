"""Deterministic pool snake-draft and bracket trees.

The model is not asked to invent these: `list_teams_seeding` returns the snake
lists, `propose_create_pool` refuses sequential blocks, and `propose_create_bracket`
lists every match (including the 3rd-place / push-in game) in its summary.
"""

from __future__ import annotations

from typing import Any

from server.tournament.utils import get_bracket_match_name, validate_bracket_name

# Two-team pools show up in unit tests and in tiny events; a 1-2 / 3-4 split is
# sequential but also the only even split of four teams into pairs. Guard the
# sizes that actually get invented wrongly: 3+ seed blocks like 1-4 vs 5-8.
_SEQUENTIAL_BLOCK_MIN = 3
# A run of one seed is trivially contiguous and tells us nothing.
_MIN_CONTIGUOUS_SEEDS = 2
# Below this, a contiguous pool is only suspicious when equal-sized pools of that
# size tile the whole field — otherwise it is a leftover, not a sequential split.
_ALWAYS_SUSPICIOUS_POOL_SIZE = 4
# Pool / Swiss / position-pool `name` is a CharField(max_length=2). The model
# likes to send "Pool A"; the UI then renders "Pool Pool A".
_STAGE_NAME_MAX = 2
_STAGE_NAME_PREFIXES = ("position pool ", "pool ", "swiss ", "group ")


def canonical_stage_name(name: str | None, fallback: str = "A") -> str:
    """Collapse 'Pool A' / 'Swiss B' to the 1-2 character label the column stores."""
    raw = (name or "").strip()
    lowered = raw.lower()
    for prefix in _STAGE_NAME_PREFIXES:
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    raw = "".join(raw.split())
    if not raw:
        raw = fallback
    return raw[:_STAGE_NAME_MAX]


def snake_pool_seeds(team_count: int, pool_count: int) -> list[list[int]]:
    """Classic snake: 1-across, reverse, 1-across, reverse, until seeds run out.

    Two pools of 4: A=[1,4,5,8], B=[2,3,6,7].
    Four pools of 4: A=[1,8,9,16], B=[2,7,10,15], C=[3,6,11,14], D=[4,5,12,13].
    """
    if team_count < 1 or pool_count < 1:
        return []
    pools: list[list[int]] = [[] for _ in range(pool_count)]
    seed = 1
    round_idx = 0
    while seed <= team_count:
        order = range(pool_count) if round_idx % 2 == 0 else range(pool_count - 1, -1, -1)
        for pool_i in order:
            if seed > team_count:
                break
            pools[pool_i].append(seed)
            seed += 1
        round_idx += 1
    return pools


def labeled_snake_pools(team_count: int, pool_count: int) -> dict[str, list[int]]:
    return {
        chr(ord("A") + i): seeds for i, seeds in enumerate(snake_pool_seeds(team_count, pool_count))
    }


def snake_draft_options(team_count: int) -> dict[str, dict[str, list[int]]]:
    """Snake tables for every pool count that still leaves at least two teams each."""
    options: dict[str, dict[str, list[int]]] = {}
    max_pools = min(team_count // 2, 6)
    for pool_count in range(2, max_pools + 1):
        options[f"{pool_count}_pools"] = labeled_snake_pools(team_count, pool_count)
    return options


def _is_contiguous(seeds: list[int]) -> bool:
    if len(seeds) < _MIN_CONTIGUOUS_SEEDS:
        return False
    ordered = sorted(int(s) for s in seeds)
    return ordered == list(range(ordered[0], ordered[-1] + 1))


def sequential_pool_seed_error(team_count: int, seeds: list[int]) -> dict[str, Any] | None:
    """Refuse 1-4 / 5-8 style blocks. Return None when the list is already a snake slice.

    A 3-seed pool on a 4-team event is a leftover, not a sequential split, so it is
    allowed. Equal-sized chunks that tile the field (2x4, 2x3, 4x4) are not.
    """
    values = [int(s) for s in seeds]
    if team_count <= len(values) or len(values) < _SEQUENTIAL_BLOCK_MIN:
        return None
    if not _is_contiguous(values):
        return None
    pool_count = max(2, (team_count + len(values) - 1) // len(values))
    tiles_the_field = pool_count * len(values) == team_count
    if len(values) < _ALWAYS_SUSPICIOUS_POOL_SIZE and not tiles_the_field:
        return None
    snake = labeled_snake_pools(team_count, pool_count)
    rendered = ", ".join(f"{name}={list_}" for name, list_ in snake.items())
    message = (
        "Pool seeds must follow snake draft, not sequential blocks like 1-4 / 5-8. "
        f"For {team_count} teams in {pool_count} pools: {rendered}."
    )
    return {"error": message, "message": message, "snake_draft": snake}


def rewrite_sequential_pool_defs(
    pool_defs: list[dict[str, Any]], team_count: int
) -> list[dict[str, Any]]:
    """If every pool is a contiguous slice of 1..n, replace them with the snake."""
    if not pool_defs or team_count < 1:
        return pool_defs
    seed_lists = [list(row.get("seeding") or []) for row in pool_defs]
    if not all(seed_lists) or not all(_is_contiguous(lst) for lst in seed_lists):
        return pool_defs
    covered = sorted(int(s) for lst in seed_lists for s in lst)
    if covered != list(range(1, team_count + 1)):
        return pool_defs
    snake = snake_pool_seeds(team_count, len(pool_defs))
    rewritten = []
    for i, row in enumerate(pool_defs):
        rewritten.append(
            {
                **row,
                "name": canonical_stage_name(row.get("name"), chr(ord("A") + i)),
                "seeding": snake[i],
            }
        )
    return rewritten


def labeled_pool_defs(pool_defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Force every pool def onto a 1-2 character name, even when seeds were already snake."""
    labeled = []
    for i, row in enumerate(pool_defs or []):
        labeled.append({**row, "name": canonical_stage_name(row.get("name"), chr(ord("A") + i))})
    return labeled


def bracket_match_plan(name: str) -> list[dict[str, Any]]:
    """The matches `build_bracket` will create for this seed-range name."""
    valid, error = validate_bracket_name(name)
    if not valid:
        raise ValueError((error or {}).get("message", "Invalid bracket name"))
    start, end = (int(part) for part in name.split("-"))
    matches: list[dict[str, Any]] = []

    def walk(lo: int, hi: int, seq: int) -> None:
        for i in range(0, ((hi - lo) + 1) // 2):
            seed_1 = lo + i
            seed_2 = hi - i
            matches.append(
                {
                    "sequence_number": seq,
                    "placeholder_seed_1": seed_1,
                    "placeholder_seed_2": seed_2,
                    "name": get_bracket_match_name(lo, hi, seed_1, seed_2),
                }
            )
        if hi - lo > 1:
            mid = lo + (((hi - lo) + 1) // 2) - 1
            walk(lo, mid, seq + 1)
            walk(mid + 1, hi, seq + 1)

    walk(start, end, 1)
    return matches


def bracket_proposal_summary(name: str, matches: list[dict[str, Any]]) -> str:
    parts = [
        f"{row['name']} {row['placeholder_seed_1']}v{row['placeholder_seed_2']}" for row in matches
    ]
    return f"Create bracket {name}: " + "; ".join(parts)
