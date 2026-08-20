"""Keep the Format section of a tournament's rules describing the real tournament.

`Tournament.rules` is one text field holding both a Format table and hand-written
policy (WFDF rules, time limits, ratio rules). Staff used to have to retype the
table by hand whenever the stages changed, and the shipped default described a
16-team event whether or not that was what they were running.

So the table is a **managed block**, fenced by the markers below and rebuilt from
the stages themselves whenever one is created or deleted. Two rules govern it:

- Only what is between the markers is ever rewritten. Everything else in the
  document belongs to staff and is never touched.
- No markers means no sync. Staff who want to write the format by hand delete the
  markers and own it from then on, and tournaments predating this feature simply
  keep whatever they already had.
"""

from __future__ import annotations

from server.tournament.models import (
    Bracket,
    CrossPool,
    Pool,
    PositionPool,
    SwissRound,
    Tournament,
)

FORMAT_BLOCK_START = "<!-- format:auto -->"
FORMAT_BLOCK_END = "<!-- /format:auto -->"

# Matches the placeholder shipped in `templates/rules_default.md`, so a tournament
# that has no stages yet reads the same before and after its first sync.
EMPTY_FORMAT = "The format appears here once the tournament's stages are created."


def _seed_range(seeds: list[int]) -> str:
    """ "1-8" for a contiguous run, "1, 3, 6, 8" when it has gaps."""
    if not seeds:
        return "—"
    if len(seeds) > 1 and seeds == list(range(seeds[0], seeds[-1] + 1)):
        return f"{seeds[0]}-{seeds[-1]}"
    return ", ".join(str(s) for s in seeds)


def _rows(tournament: Tournament) -> list[tuple[str, str, str]]:
    """(stage, seeds, note) for every stage, in the order they are played.

    Every value here comes off the stage row itself. Nothing reads the stage's
    matches: game counts and durations shift constantly during an event, and
    tracking them meant rewriting this table once per match created. One stage,
    one row, one write.
    """
    rows: list[tuple[str, str, str]] = []

    for pool in Pool.objects.filter(tournament=tournament).order_by("sequence_number"):
        seeds = sorted(int(s) for s in (pool.initial_seeding or {}))
        rows.append(
            (f"Pool {pool.name}", _seed_range(seeds), "Round-robin, re-seed within the pool")
        )

    for swiss in SwissRound.objects.filter(tournament=tournament).order_by("sequence_number"):
        seeds = sorted(int(s) for s in (swiss.initial_seeding or {}))
        rounds = "round" if swiss.num_rounds == 1 else "rounds"
        rows.append((f"Swiss {swiss.name}", _seed_range(seeds), f"{swiss.num_rounds} {rounds}"))

    for _cross in CrossPool.objects.filter(tournament=tournament).order_by("id"):
        rows.append(("Cross-Pool", "—", "Winner takes the higher seed"))

    for bracket in Bracket.objects.filter(tournament=tournament).order_by("sequence_number"):
        seeds = sorted(int(s) for s in (bracket.initial_seeding or {}))
        rows.append((f"Bracket {bracket.name}", _seed_range(seeds), "Winner takes the higher seed"))

    for position in PositionPool.objects.filter(tournament=tournament).order_by("sequence_number"):
        seeds = sorted(int(s) for s in (position.initial_seeding or {}))
        rows.append(
            (
                f"Position Pool {position.name}",
                _seed_range(seeds),
                "Round-robin, re-seed within the band",
            )
        )

    return rows


def render_format_table(tournament: Tournament) -> str:
    """The Format section body — a markdown table, or a note when nothing exists yet."""
    rows = _rows(tournament)
    if not rows:
        return EMPTY_FORMAT

    header = ["| Stage | Seeds | Notes |", "| :---- | :---- | :---- |"]
    body = [f"| **{stage}** | {seeds} | {note} |" for stage, seeds, note in rows]
    teams = tournament.teams.count()
    caption = (
        f"\n{teams} teams. Stages are listed in the order they are played."
        if teams
        else "\nStages are listed in the order they are played."
    )
    return "\n".join(header + body) + "\n" + caption


def render_format_block(tournament: Tournament) -> str:
    return f"{FORMAT_BLOCK_START}\n{render_format_table(tournament)}\n{FORMAT_BLOCK_END}"


def sync_rules_format(tournament: Tournament) -> bool:
    """Rewrite the managed Format block. Returns whether anything changed.

    A tournament whose rules carry no markers is left completely alone — that is
    both the opt-out for staff who write their own format and what keeps
    tournaments created before this feature from being rewritten underneath them.
    """
    rules = tournament.rules or ""
    start = rules.find(FORMAT_BLOCK_START)
    end = rules.find(FORMAT_BLOCK_END, start + 1)
    if start == -1 or end == -1:
        return False

    updated = rules[:start] + render_format_block(tournament) + rules[end + len(FORMAT_BLOCK_END) :]
    if updated == rules:
        return False

    tournament.rules = updated
    # `update_fields` so this never races with a concurrent write to seeding or
    # status — the stage that triggered us may be mid-save on the same tournament.
    tournament.save(update_fields=["rules"])
    return True


# Phrases unique to the Format table that shipped in `rules_default.md`. Every
# tournament created before the managed block carries a verbatim copy of it, and it
# has been byte-stable across all three revisions of the template. A table still
# containing all of these is one nobody has edited, so it is safe to take over.
LEGACY_TABLE_SIGNATURES = ("**Pool Games**", "4 Pools of 4", "1-4, 5-12, 13-16")


def _format_section_bounds(lines: list[str]) -> tuple[int, int] | None:
    """(first, last) line indices of the `## Format` section body, end-exclusive."""
    for i, line in enumerate(lines):
        if line.strip().lower() == "## format":
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("## "):
                    return i + 1, j
            return i + 1, len(lines)
    return None


def _table_bounds(lines: list[str], start: int, end: int) -> tuple[int, int] | None:
    """(first, last) line indices of the markdown table inside a section."""
    first = next((i for i in range(start, end) if lines[i].lstrip().startswith("|")), None)
    if first is None:
        return None
    last = first
    while last < end and lines[last].lstrip().startswith("|"):
        last += 1
    return first, last


def upgrade_legacy_format_block(rules: str | None) -> str | None:
    """Put markers around a stock, never-edited Format table.

    Returns the new rules text, or None when nothing should change — markers
    already present, no `## Format` section, no table in it, or a table someone has
    edited. Only the table lines are replaced, so prose staff wrote around it
    survives untouched.

    Kept a pure string function so the backfill migration stays a thin caller and
    the interesting cases are unit-testable without building a tournament.
    """
    if not rules:
        return None
    if FORMAT_BLOCK_START in rules or FORMAT_BLOCK_END in rules:
        return None  # already managed

    lines = rules.splitlines()
    section = _format_section_bounds(lines)
    if section is None:
        return None
    table = _table_bounds(lines, *section)
    if table is None:
        return None

    first, last = table
    body = "\n".join(lines[first:last])
    if not all(signature in body for signature in LEGACY_TABLE_SIGNATURES):
        return None  # edited by hand — leave the whole document alone

    managed = [FORMAT_BLOCK_START, EMPTY_FORMAT, FORMAT_BLOCK_END]
    updated = lines[:first] + managed + lines[last:]
    trailing = "\n" if rules.endswith("\n") else ""
    return "\n".join(updated) + trailing


__all__ = [
    "EMPTY_FORMAT",
    "FORMAT_BLOCK_END",
    "FORMAT_BLOCK_START",
    "LEGACY_TABLE_SIGNATURES",
    "upgrade_legacy_format_block",
    "render_format_block",
    "render_format_table",
    "sync_rules_format",
]
