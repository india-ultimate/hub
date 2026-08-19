---
name: format_playbooks
status: active
always: false
priority: 10
when_status: [DFT, SCH]
triggers:
  [
    set up,
    setup,
    configure,
    format,
    pools,
    swiss,
    bracket,
    cross pool,
    crossover,
    position pool,
    structure,
    snake,
    seeding order,
    re-seed,
    reseed
  ]
requires_tools:
  [
    list_teams_seeding,
    list_stages,
    list_pools,
    list_brackets,
    propose_update_seeding,
    propose_create_pool,
    propose_create_swiss_round,
    propose_create_cross_pool,
    propose_create_cross_pool_matches,
    propose_create_bracket,
    propose_create_position_pool,
    propose_full_setup,
    propose_start_tournament,
    ask_user
  ]
---

# Format playbooks

How India Ultimate tournaments are actually structured. Grounded in 76 completed hub tournaments
(2023–2026): NCS/NOCS/NWCS nationals and regionals, sectionals, beach nationals, and open hat/club
events, 4–31 teams.

## Pick by team count

Confirm with staff only when two families are genuinely both common.

| Teams | Structure (most common in production)                                                                          | Brackets / position pools                                             |
| ----- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 4     | 1 pool of 4 (RR)                                                                                               | `1-4`, or `1-2` + `3-4` finals                                        |
| 5     | 1 pool of 5 (RR)                                                                                               | `1-4`, or CP (2v3, 4v5) then `1-2` + `3-4`                            |
| 6     | 1 pool of 6 (full RR, 5 games/team over 2 days) **or** 2×3 pools + CP                                          | `1-6` full placement, or `1-2`/`3-4`/`5-6`, or `1-4` + `5-6`          |
| 7     | 1 pool of 7 (pure RR, often no bracket) **or** 4+3 pools                                                       | `1-2`, `3-4`, `5-6` placement pairs                                   |
| 8     | 2×4 pools → full crossover CP → brackets                                                                       | `1-4` + `5-8` (or single `1-8`)                                       |
| 9     | 5+4 pools → CP → bracket + PP                                                                                  | `1-4` + `5-6`, position pool of 3 for 7–9                             |
| 10    | 2×5 pools → CP (3v6, 4v5, 7v10, 8v9)                                                                           | `1-4` + `5-8` + `9-10`                                                |
| 11    | 3+4+4 pools → CP                                                                                               | `1-8`, position pool of 3                                             |
| 12    | **4×3 pools → CP → `1-8` + position pool 9–12** (canonical, 4 events). Alt: 2×6 pools → `1-4` + `5-8` + PP     | `1-8` + PP(9,10,11,12)                                                |
| 13–15 | 4 pools of 3/4 → CP → `1-8` + PPs for the rest                                                                 | e.g. 13t: `1-8` + PP(9–13)                                            |
| 16    | **4×4 pools → CP bands 1–4 / 5–12 / 13–16 → `1-8` + `9-16`** (canonical nationals format, 5 events verbatim)   | `1-8` + `9-16`                                                        |
| 17–18 | 5+4+4+4 pools → CP → `1-8` + lower brackets/PPs                                                                | e.g. `1-8`, `9-12`, `13-14`, `16-17`; or `1-8` + PP(9–13) + PP(14–18) |
| 19–20 | 5 pools (4/3) or 4×5 → multi-round CP                                                                          | `1-8` + `9-12`/`9-16` + PPs of 3–4                                    |
| 24    | 6×4 pools → 2 CP rounds → six brackets of 4 (`1-4` … `21-24`) **or** 24-team Swiss, 5 rounds → placement pairs | brackets of 4, or `1-4` + pairs `5-6` … `23-24`                       |
| 25+   | Mixed pool sizes (5s and 4s) → CP chains → `1-8`, `9-16`, `17-24`, … + PP for remainder                        | seen at 31 teams                                                      |

Rules of thumb:

- Prefer 4 pools once you have ≥12 teams; prefer pools of 4, using pools of 3 or 5 to absorb
  remainders. Seed pools by snake: pool A gets 1, 8, 9, 16; B gets 2, 7, 10, 15; and so on.
- Brackets are always contiguous seed-range names (`"1-8"`, `"9-16"`, `"5-6"`) spanning an **even**
  number of seeds — an odd span is rejected. Sizes 2, 4 and 8 dominate. Never invent names like
  "Top 8".
- Position pools mop up non-power-of-2 leftovers (3–5 teams) as a round-robin, named with a single
  letter continuing after the pools (pools A–D → PPs E, K, …). Usually the bottom band, occasionally
  a top band of 4 instead of a bracket.
- Swiss appears in two shapes: one whole-field group (24 teams, 5 rounds), or a split into two
  groups of 8 by odd/even seeds (16-team beach, 4 rounds each). Swiss feeds cross-pool or placement
  brackets exactly like pools do.
- Series events (NCS/NOCS/NWCS) follow these formats most strictly; open and hat events vary more —
  for a non-series event with an unusual count, ask rather than force a template.

## Cross-pool pairings

Cross-pool is a reseeding round between pools and brackets. Creating the stage creates **no
matches** — propose the exact pairings separately.

Production pairings, in placeholder seeds after the pool reseed:

- **16 teams (canonical, 5 nationals):** band 1–4: `1v3, 2v4`; band 5–12: `5v12, 6v11, 7v10, 8v9`;
  band 13–16: `13v15, 14v16`. Variant: `1v2, 3v4` and `13v14, 15v16`.
- **12 teams:** `1v3, 2v4, 5v12, 6v11, 7v10, 8v9` (some events skip the top band).
- **8 teams:** full crossover `1v8, 2v7, 3v6, 4v5` before `1-4`/`5-8`.
- **Small (5–7 teams):** middle crossovers only — `2v3, 4v5` at 5 teams; `3v5, 4v6` or `3v6, 4v5`
  at 6–7. Seeds 1 and often 2 skip straight to the final or bracket.
- **19+ teams:** chained bands over two CP rounds, e.g. `9v16, 10v15, 11v14, 12v13`, then
  `13v20, 14v19, 15v17, 16v18` — winners move up a band before brackets.

The pattern: winners of the `5v12` band enter `1-8`, losers drop to `9-16`. Middle bands get
crossed; the very top and very bottom get short two-game bands, or none.

## Seeding and creation order

- Tournament seeding is `{"1": team_id, …}` and pools and Swiss groups require it. If it is empty,
  ask staff for the order (or derive it from the previous event in the series if they give you one)
  and propose it first.
- Seeding is safe to change any time **before** the tournament starts — it resyncs pool and Swiss
  snapshots for you, so a re-seed does not mean rebuilding stages. After it starts, seeding moves
  only through results.
- A pool redistributes **its own** seed set by finish order: a pool holding seeds {2, 8, 10, 16}
  gives 2 to its winner and 8 to its runner-up. Finishing first in a weak pool does not make a team
  the 1 seed.
- Create in this order: pools or Swiss (seq 1..n) → cross-pool → brackets (seq 1..n, top bracket
  first) → position pools. Build everything up front; matches sit unscheduled until you place them.

## Proposal sequences

**"Set up our 16-team event"**

1. Read state. If seeding is empty → ask for the order → `propose_update_seeding`.
2. `propose_full_setup` with 4 snake-seeded pools (A–D) and `bracket_names=["1-8","9-16"]`, or the
   equivalent individual proposals.
3. `propose_create_cross_pool`, then `propose_create_cross_pool_matches` with
   `[[1,3],[2,4],[5,12],[6,11],[7,10],[8,9],[13,15],[14,16]]`.
4. If staff mention more fields than exist, `propose_create_field` for each.
5. `propose_start_tournament` when they are ready to go live.

**"12 teams, 2 days, 4 fields, NOCS regionals"** — no question needed. 4 pools of 3, CP
`1v3, 2v4, 5v12, 6v11, 7v10, 8v9`, bracket `1-8`, position pool E for seeds 9–12.

**"Add a Top 8 after Swiss"** (20-team Swiss, final round done) — `get_standings` to confirm Swiss
is complete, `propose_create_bracket("1-8", 1)`, ask whether they want `9-16` or position pools for
the rest, then `propose_generate_fixtures` to fill teams. The new matches are created unscheduled.

## Anti-patterns

- A bracket size that does not match the seed band — a `1-8` when only 6 teams can reach it. Use
  `1-4` plus pairs, or a position pool.
- Creating cross-pool and expecting matches to appear.
- Inventing bracket names, or an odd seed span.
- Forcing a canonical template onto an open or hat event with an unusual count — ask.
- Renaming or re-numbering stages mid-event.
