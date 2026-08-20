---
name: format_playbooks
status: active
always: false
priority: 10
when_phase: [no_stages]
triggers:
  [
    set up,
    setup,
    configure,
    format,
    pool,
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
    reseed,
    pairing,
    pairings,
    1v8,
    3v6
  ]
requires_tools:
  [
    list_teams_seeding,
    list_stages,
    list_pools,
    list_brackets,
    list_matches,
    propose_update_seeding,
    propose_create_pool,
    propose_create_swiss_round,
    propose_create_cross_pool,
    propose_create_cross_pool_matches,
    propose_create_bracket,
    propose_create_position_pool,
    propose_full_setup,
    propose_update_match_seeds,
    propose_start_tournament,
    propose_create_field,
    ask_user
  ]
---

# Format playbooks

How India Ultimate tournaments are structured. Copy these defaults; do not invent a layout.

## Snake seeding (always)

Pools are snake-drafted from tournament seeds. `list_teams_seeding` returns `snake_draft` — copy
those lists. Never sequential blocks (A=1–4, B=5–8); those are refused.

| Pools  | Seeds                                                          |
| ------ | -------------------------------------------------------------- |
| 2 of 4 | A=`[1,4,5,8]` B=`[2,3,6,7]`                                    |
| 4 of 4 | A=`[1,8,9,16]` B=`[2,7,10,15]` C=`[3,6,11,14]` D=`[4,5,12,13]` |
| 4 of 3 | A=`[1,8,9]` B=`[2,7,10]` C=`[3,6,11]` D=`[4,5,12]`             |

## Brackets include the push-in

`propose_create_bracket("1-4")` creates **four** matches. The 3v4 game is the 3rd-place / push-in;
it is not optional and it is not a separate bracket.

| Bracket | Matches created                                              |
| ------- | ------------------------------------------------------------ |
| `1-4`   | 1v4, 2v3 (semis); 1v2 (final); **3v4 (3rd place / push-in)** |
| `5-8`   | 5v8, 6v7; 5v6 (5th); 7v8 (7th)                               |
| `1-8`   | Quarters 1v8…4v5, then the `1-4` and `5-8` trees above       |

Never describe a `1-4` as "two semis and a final". Never add a `3-4` bracket to supply the push-in.
Names are always contiguous even ranges (`"1-4"`, `"9-16"`), never "Top 8".

Default first-round pairings are 1vN, 2vN-1, and so on. Staff sometimes want a different draw —
1v8 and 2v7 kept, but 3v5 and 4v6 instead of 3v6 and 4v5. `list_matches`, then one
`propose_update_match_seeds` that rewrites **every** pairing that changes. Later-round matches
(1v4, 2v3, 5v8, …) stay put: those numbers are slots the winners flow into, not a replay of who
met in the quarters. A seed may appear only once in the same round, so never change 3v6 to 3v5
without also moving 4v5. Completed matches cannot be re-seeded.

## Staff delegating is still an ask

"Whatever you think is best", "pools or Swiss, I'm open", "you decide" — these are not decisions.
The initial format determines every match of the event, so put the two options to staff with
`ask_user` and wait. Recommend one in the option description if you have a view; do not propose a
stage until they have picked.

## Pick by team count

Confirm with staff only when two families are both common.

| Teams | Structure                                                     | After pools                               |
| ----- | ------------------------------------------------------------- | ----------------------------------------- |
| 4     | 1 pool of 4                                                   | `1-4`                                     |
| 5     | 1 pool of 5                                                   | `1-4`, or CP 2v3/4v5 then `1-2`+`3-4`     |
| 6     | 1 pool of 6 **or** 2×3 + CP                                   | `1-4` + `5-6`, or full placement          |
| 7     | 1 pool of 7 **or** 4+3                                        | `1-2`, `3-4`, `5-6` pairs, or `1-4`       |
| 8     | 2×4 snake pools → CP `1v8,2v7,3v6,4v5` → `1-4` + `5-8`        | both 4-team brackets (each has a push-in) |
| 9     | 5+4 snake → CP → `1-4` + `5-6` + PP of 3 for 7–9              |                                           |
| 10    | 2×5 snake → CP (3v6, 4v5, 7v10, 8v9) → `1-4` + `5-8` + `9-10` |                                           |
| 12    | **4×3 snake → CP → `1-8` + PP 9–12**                          |                                           |
| 16    | **4×4 snake → CP bands 1–4 / 5–12 / 13–16 → `1-8` + `9-16`**  |                                           |

Prefer 4 pools at ≥12 teams; pools of 4, with 3s or 5s for remainders. Position pools mop up
non-power-of-2 leftovers (3–5 teams). Swiss is a whole-field group or two odd/even groups of 8.

## Cross-pool pairings

Creating the CP stage creates **no matches** — propose pairings separately, in placeholder seeds
after the pool reseed.

- **8 teams:** `1v8, 2v7, 3v6, 4v5` then `1-4` / `5-8`.
- **12 teams:** `1v3, 2v4, 5v12, 6v11, 7v10, 8v9`.
- **16 teams:** `1v3, 2v4`; `5v12, 6v11, 7v10, 8v9`; `13v15, 14v16`.
- **Small (5–7):** middle only — `2v3, 4v5` at 5; seeds 1 (and often 2) skip to the final/bracket.

Winners of the 5v12 band enter `1-8`, losers drop to `9-16`.

## Seeding and creation order

Tournament seeding is `{"1": team_id, …}`. If it is empty, ask for the order and propose it first.
Seeding is safe to change before start — it resyncs pool and Swiss snapshots. After start, seeds
move only through results. A pool redistributes **its own** seed set by finish order.

Create: **fields first**, then snake-seeded pools or Swiss → cross-pool → brackets (top first) →
position pools. Matches stay unscheduled until a later turn.

## Proposal sequences

**"Set up our 16-team event"** — fields (stop if none) → snake 4 pools from `snake_draft` plus
`1-8`/`9-16` and the 16-team CP pairs → one schedule → start when asked.

**"12 teams, 2 days, 4 fields, NOCS regionals"** — 4 pools of 3 (snake), CP as above, `1-8`,
position pool E for 9–12.

**"Add a Top 8 after Swiss"** — `get_standings`, `propose_create_bracket("1-8", 1)` (placement
games included), ask about the rest, `propose_generate_fixtures`.

## Anti-patterns

- Sequential pool seeds (`[1,2,3,4]` / `[5,6,7,8]`).
- Naming a pool `"Pool A"` — the name is `A` or `B` (one or two characters). The UI already prefixes
  "Pool".
- Describing or building a `1-4` as two semis and a final, or adding a `3-4` for the push-in.
- Changing one first-round pairing (3v6 → 3v5) without rewriting the match that still holds the
  displaced seed.
- A bracket larger than the seeds that can reach it.
- Creating cross-pool and expecting matches to appear.
- Inventing bracket names, or an odd seed span.
- Forcing a canonical template onto an open or hat event with an unusual count — ask.
- Renaming or re-numbering stages mid-event.
