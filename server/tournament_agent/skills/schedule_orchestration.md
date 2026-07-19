# Tournament schedule orchestration skill

How India Ultimate tournaments are actually structured and scheduled. Grounded in 76
completed hub tournaments (2023–2026): NCS/NOCS/NWCS nationals and regionals, sectionals,
beach nationals, and open hat/club events (4–31 teams). Use this whenever you recommend or
propose stage structure, fixtures, or schedules.

## Hard rules

- Never mutate live data directly. Every change goes through a `propose_*` tool and staff
  Confirm in the UI. Reads (`get_*`, `list_*`) are always safe.
- Always read current state first: `get_tournament_overview`, `list_teams_seeding`,
  `list_fields`, and the relevant stage lists. Never assume stages or seeding exist.
- Ask (`ask_user`) before inventing anything ambiguous or irreversible: number of days,
  format family when team count is unusual, bracket depth. Do not ask about things this
  skill gives a safe default for.
- One field cannot host two matches at the same start time (DB-enforced unique
  tournament+time+field).
- All times are IST wall-clock. Pass naive ISO strings (e.g. `2026-07-18T07:00:00`).
- Do not include player names/emails in any output. Team names are fine.

## What each proposal actually does (do not guess)

| Tool | Effect on Confirm |
|---|---|
| `propose_update_seeding` | Sets tournament seeding map `{"1": team_id, ...}`. Required before pools. |
| `propose_create_pool(name, seq, seeding=[seeds])` | Creates pool **and its round-robin matches** (unscheduled, YTF). |
| `propose_create_swiss_round(name, seeding, num_rounds)` | Creates Swiss group and its matches. |
| `propose_create_cross_pool()` | Creates the cross-pool stage **only — no matches**. Follow up with `propose_create_cross_pool_matches`. |
| `propose_create_cross_pool_matches(seed_pairs, sequence_number=1)` | Creates the individual seed-pair matches, e.g. `[[1,3],[2,4],[5,12]]` (unscheduled, YTF). Requires the cross-pool stage to exist. Use `sequence_number=2` for a second CP round. |
| `propose_create_bracket(name, seq)` | Name must be a seed range string `"1-8"`. Creates all bracket matches including placement games. |
| `propose_create_field(name, address?, is_broadcasted?)` | Adds a playing field (e.g. `"Field 3"`). Propose fields before scheduling if the staff mention more fields than exist. |
| `propose_create_position_pool(name, seq, seeding=[seeds])` | Round-robin among those seed numbers. |
| `propose_start_tournament` | Assigns teams into pool/Swiss round-1 matches from seeding; tournament goes LIVE. |
| `propose_generate_fixtures` | Advances progression: pairs the next Swiss round, fills teams into cross-pool/bracket/position-pool matches once the prior stage completes. Creates no new matches. |
| `propose_recommended_schedule(...)` | Deterministic greedy scheduler over unscheduled matches (single duration, day window, lunch, min rest, fields). |
| `propose_bulk_schedule(assignments)` / `propose_update_match` | Exact time/field/duration control. |

## Format playbooks (mined from production)

Pick by team count; confirm with the user only when two families are both common.

| Teams | Structure (most common in production) | Brackets / position pools |
|---|---|---|
| 4 | 1 pool of 4 (RR) | `1-4`, or `1-2` + `3-4` finals |
| 5 | 1 pool of 5 (RR) | `1-4`, or CP (2v3, 4v5) then `1-2` + `3-4` |
| 6 | 1 pool of 6 (full RR, 5 games/team over 2 days) **or** 2×3 pools + CP | `1-6` full placement, or `1-2`/`3-4`/`5-6`, or `1-4` + `5-6` |
| 7 | 1 pool of 7 (pure RR, often no bracket) **or** 4+3 pools | `1-2`, `3-4`, `5-6` placement pairs |
| 8 | 2×4 pools → full crossover CP → brackets | `1-4` + `5-8` (or single `1-8`) |
| 9 | 5+4 pools → CP → bracket + PP | `1-4` + `5-6`, position pool of 3 for 7–9 |
| 10 | 2×5 pools → CP (3v6, 4v5, 7v10, 8v9) | `1-4` + `5-8` + `9-10` |
| 11 | 3+4+4 pools → CP | `1-8`, position pool of 3 |
| 12 | **4×3 pools → CP → `1-8` + position pool 9–12** (canonical, 4 events). Alt: 2×6 pools → `1-4` + `5-8` + PP | `1-8` + PP(9,10,11,12) |
| 13–15 | 4 pools of 3/4 → CP → `1-8` + PPs for the rest | e.g. 13t: `1-8` + PP(9–13) |
| 16 | **4×4 pools → CP bands 1–4 / 5–12 / 13–16 → `1-8` + `9-16`** (canonical nationals format, 5 events verbatim) | `1-8` + `9-16` |
| 17–18 | 5+4+4+4 pools → CP → `1-8` + lower brackets/PPs | e.g. `1-8`, `9-12`, `13-14`, `16-17`; or `1-8` + PP(9–13) + PP(14–18) |
| 19–20 | 5 pools (4/3) or 4×5 → multi-round CP | `1-8` + `9-12`/`9-16` + PPs of 3–4 |
| 24 | 6×4 pools → 2 CP rounds → six brackets of 4 (`1-4` … `21-24`) **or** 24-team Swiss, 5 rounds → placement pairs | brackets of 4, or `1-4` + pairs `5-6` … `23-24` |
| 25+ | Mixed pool sizes (5s and 4s) → CP chains → `1-8`, `9-16`, `17-24`, … + PP for remainder | seen at 31 teams |

Rules of thumb:
- Prefer 4 pools once you have ≥12 teams; prefer pools of 4, use pools of 3 or 5 to absorb
  remainders. Seed pools by snake: pool A gets 1,8,9,16; B gets 2,7,10,15; etc. (visible in
  production `initial_seeding`: A={1,7,9,15}-style serpentine).
- Brackets are always contiguous seed-range names (`"1-8"`, `"9-16"`, `"5-6"`). Sizes 2, 4,
  8 dominate; size 6 exists but is rare. Never invent names like "Top 8".
- Position pools mop up non-power-of-2 leftovers (3–5 teams) as a round-robin, named with a
  single letter continuing after the pools (pools A–D → PPs E, K, …). They usually cover the
  bottom band (9–12, 13–16 leftovers), occasionally a top band of 4 instead of a bracket.
- Swiss appears in two shapes: one whole-field group (24 teams, 5 rounds) or a split into 2
  groups of 8 by odd/even seeds (16-team beach, 4 rounds each). Swiss feeds cross-pool or
  placement brackets exactly like pools do.
- Series events (NCS/NOCS/NWCS) follow these formats most strictly; open/hat events vary
  more — for a non-series event with an unusual count, ask rather than force a template.

## Cross-pool guidance

Cross-pool is a reseeding round between pools and brackets. Creating the stage creates no
matches — propose the exact seed pairings with `propose_create_cross_pool_matches`; after
pools complete, `propose_generate_fixtures` fills teams into those matches.

Production pairings (placeholder seeds after pool reseed):

- **16 teams (canonical, 5 nationals):** band 1–4: `1v3, 2v4`; band 5–12: `5v12, 6v11,
  7v10, 8v9`; band 13–16: `13v15, 14v16`. Variant: `1v2, 3v4` and `13v14, 15v16`.
- **12 teams:** `1v3, 2v4, 5v12, 6v11, 7v10, 8v9` (some events skip the top band).
- **8 teams:** full crossover `1v8, 2v7, 3v6, 4v5` before `1-4`/`5-8` brackets.
- **Small (5–7 teams):** middle crossovers only, e.g. `2v3, 4v5` (5 teams); `3v5, 4v6`
  or `3v6, 4v5` (6–7 teams). Seeds 1 (and often 2) skip straight to the final/bracket.
- **19+ teams:** chained bands over two CP rounds, e.g. `9v16, 10v15, 11v14, 12v13`
  then `13v20, 14v19, 15v17, 16v18` (winners move up a band before brackets).

The pattern: winners of `5v12`-band games enter the `1-8` bracket, losers drop to `9-16`.
Middle bands get crossed; the very top and very bottom get short 2-game bands or none.

## Seeding & progression

- Tournament seeding is `{"1": team_id, ...}`. Pools/Swiss require it — propose
  `propose_update_seeding` first if empty (ask staff for the order or derive from series
  rankings if they give them).
- Pool finish order reseeds **within the pool's own original seed set** (WFDF style), not by
  global W/L across pools. E.g. pool with seeds {2,8,10,16}: its winner takes 2, runner-up 8.
- On cross-pool and bracket upsets the lower seed winning **swaps** the two seeds in
  `current_seeding`.
- Progression is: complete a stage's matches → `propose_generate_fixtures` → next stage's
  placeholders fill. Propose it after each completed round when staff ask to "advance".
- Order of structure creation: pools/Swiss (seq 1..n) → cross-pool → brackets (seq 1..n,
  top bracket first) → position pools. Create everything up front at setup time; matches sit
  as YTF until scheduled. Completed production events almost always end with zero YTF —
  surface any unscheduled matches (`list_matches`, overview `unscheduled_match_count`).

## Scheduling playbook (production numbers)

**Durations** (grass; halve-ish for beach/5v5, which run 25–65 min):

| Stage | Default | Notes |
|---|---|---|
| Pool / Swiss | 75 min | 60 min when a 2-day event must fit 6 pool rounds in day 1 (sectionals) |
| Cross-pool | 75 min | same as pools |
| Bracket | 75 min | semis/finals 90 min; flagship nationals used 100 min for all brackets |
| Position pool | 75 min | mirrors pool duration |

**Slot spacing:** round start-to-start = duration + 10–15 min buffer. 75-min games on
90-min slots is the single most common grid (80+ observed rounds); 60-min games on 70–75
min slots.

**Day window:** first pull 06:00–07:30 (mode 07:00; 06:00–06:30 for hot-season or heavy
slates). Last game ends 17:15–18:30. A 09:00 start is unusual in production — use 07:00
unless staff say otherwise. Never schedule past ~18:30 without staff confirming lights.

**Lunch:** about half of full days take a 60–90 min midday break (no starts roughly
12:30–14:30); the rest run straight through with the 15-min buffers. Take the break when
the slate fits comfortably; drop it when a 2-day event needs 6+ rounds in a day. Scheduler
defaults `lunch 13:00–14:00` are acceptable; production breaks often sit 12:00–15:00.

**Rest:** minimum same-day gap between one team's games: 60 min after game end (production
per-event minima cluster 60–75; overall median gap 105). Never go below 30.

**Team load:** pools day ≈ 3 games/team (4 short games only with 60-min slots); middle
day 2–3; finals day 1–2. Do not exceed 4 games/team/day.

**Fields:** named `Field 1..N` by default (venue-specific like `MG1`, `Grass 1` when staff
say so). 2–4 fields typical. 4–8 matches per field per day is the healthy band; >9 on grass
is an overpacked red flag.

**Multi-day packing** (dominant production layouts):

| Days | Day 1 | Day 2 | Day 3 |
|---|---|---|---|
| 2 | all pool rounds (evening CP if pools finish early) | CP first thing → brackets → placement/finals | — |
| 3 | all pool rounds | CP in the morning → opening brackets (QF / 9-16 R1) | remaining brackets + position pools; finals start 14:30–16:30 |

Brackets never start before their feeding pools/CP are complete. Finals go last, often on
a marquee field, with the day tapering (fewer matches, later starts).

## Scheduler usage

`propose_recommended_schedule` applies **one duration to every unscheduled match** and
packs greedily. So schedule stage-by-stage:

1. Pools: `propose_recommended_schedule(start_date=day1, end_date=day1, duration_mins=75,
   min_rest_mins=60, day_start_hour=7, day_end_hour=18, field_ids=[...])`.
2. Later stages: either run it again per day once earlier matches are placed, or build the
   grid yourself and use `propose_bulk_schedule` — required whenever brackets need a longer
   duration (90/100) than pools.
3. Fix individual slots with `propose_update_match`.
4. Sanity-check with `get_schedule_grid` / `list_matches`: no double-booked field slots, no
   team below min rest, brackets after their feeder stage's last slot.

Note the scheduler cannot enforce rest for placeholder matches (no teams yet) — keep bracket
rounds ≥ one slot apart yourself.

## Question policy

Ask via `ask_user` (single question, concrete options) only for:

- **Number of days / dates** if the event window is ambiguous.
- **Format family** when the team count genuinely splits (e.g. 12: 4×3+CP+`1-8` vs 2×6;
  24: pools+CP vs Swiss; 6–7: single RR vs pools+placement).
- **Bracket depth** when teams ≥ 16 and staff haven't implied it (`1-8`+`9-16` vs `1-8`+PPs).
- **Game length** only if the slate doesn't fit the window at 75 min — offer 60 min or an
  earlier start.
- **Lights / late finish** before scheduling anything past 18:30.

Do NOT ask about: lunch, buffer, rest, field naming, snake seeding, CP pairings for
canonical counts (8/12/16), start time (default 07:00), or bracket naming. Defaults above
are production-safe. When you apply a default silently, state it in your summary so staff
can object before confirming.

## Proposal sequences

**"Set up our 16-team event" (structure):**
1. Read state. If seeding empty → ask for seed order → `propose_update_seeding`.
2. `propose_full_setup` with 4 snake-seeded pool_defs (A–D) and
   `bracket_names=["1-8","9-16"]` — or the equivalent individual `propose_create_pool` ×4 +
   `propose_create_bracket` ×2.
3. `propose_create_cross_pool`, then `propose_create_cross_pool_matches` with the canonical
   pairings `[[1,3],[2,4],[5,12],[6,11],[7,10],[8,9],[13,15],[14,16]]`.
4. If staff mention more fields than exist (`list_fields`), `propose_create_field` for each.
5. `propose_start_tournament` when staff are ready to go live.

**"Recommend a weekend schedule":**
1. `list_matches(unscheduled)` + `list_fields`.
2. Day 1 pools via `propose_recommended_schedule` (75 min, 07:00 start).
3. Day 2 CP at 07:00, then brackets on duration+15 slots via `propose_bulk_schedule`
   (90–100 min brackets if staff want long finals), finals last.
4. Summarize per-team load, rest minima, and per-field counts in the proposal message.

**"Create Top 8 / 9–16 after pools":**
1. `get_standings` to confirm pools are COM.
2. `propose_create_bracket("1-8", 1)` and `propose_create_bracket("9-16", 2)` if missing.
3. `propose_generate_fixtures` to fill teams from current seeding.
4. Then schedule the new matches (they are created YTF).

## Anti-patterns (seen avoided in production)

- Brackets or CP scheduled before the feeding stage's last match ends.
- More than 4 games per team per day, or same-day gaps under 60 min.
- >9 matches on one field in a day; uneven fields (one idle, one packed).
- Starting a full slate at 09:00 (loses two rounds vs the production 07:00 norm) or
  running past 18:30 without lights.
- Bracket size that doesn't match the seed band (a `1-8` bracket when only 6 teams can
  reach it — use `1-4` + pairs or a position pool).
- Creating cross-pool and expecting matches to appear; forgetting `propose_generate_fixtures`
  after a stage completes (placeholders stay empty).
- Renaming or re-numbering stages mid-event; proposing schedule changes for COM matches.

## Worked examples

**A. "16 mixed teams this weekend on 3 fields — set it up and schedule it."**
Read state; seeding present; Sat–Sun confirmed from event dates → ask nothing except one
question if pools can't fit: 16 teams = 24 pool matches = 8 rounds of 3 fields; at 75/90-min
slots that's 07:00–19:00 — too long, so ask: "60-min pool games, or extend pools into Sunday
morning?" Then: full setup (4 pools snake, CP, `1-8`+`9-16`) → recommend CP pairings →
schedule day 1 pools, day 2 CP 07:00 + brackets, finals ~15:30 → `propose_start_tournament`.

**B. "12 teams, 2 days, 4 fields, NOCS regionals."**
No question needed. 4 pools of 3 (12 matches, 3 rounds on 4 fields), CP `1v3,2v4,5v12,
6v11,7v10,8v9`, bracket `1-8`, position pool E = seeds 9–12. Day 1: pools 07:00–11:15 at
90-min slots, lunch, CP in two rounds 13:00 and 14:30. Day 2: `1-8` QFs 07:00, semis, PP
round-robin in parallel, final ~14:30, all 75 min.

**C. "Add a Top 8 after Swiss" (20-team Swiss, round 5 of 5 done).**
`get_standings` → Swiss complete. `propose_create_bracket("1-8", 1)`; suggest `9-16` or
position pools for the rest and ask which staff want. `propose_generate_fixtures` to fill
teams, then `propose_bulk_schedule` for tomorrow at 90-min slots with 90-min semis/final.
