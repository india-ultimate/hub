---
name: scheduling_playbook
status: active
always: false
priority: 15
triggers:
  [
    schedule,
    scheduling,
    slot,
    slots,
    fields,
    lunch,
    rest,
    duration,
    minute games,
    weekend,
    saturday,
    sunday,
    day 1,
    day 2,
    grid,
    kick off,
    first pull,
    marquee
  ]
requires_tools:
  [
    list_matches,
    list_fields,
    list_stages,
    check_schedule_conflicts,
    propose_recommended_schedule,
    propose_bulk_schedule,
    propose_update_match,
    propose_create_field,
    propose_update_field,
    propose_delete_field,
    ask_user
  ]
---

# Scheduling playbook

Production numbers from 76 completed hub tournaments. These are defaults you apply and state, not
things to ask about.

## Durations

Grass; roughly halve for beach and 5v5, which run 25–65 minutes.

| Stage         | Default | Notes                                                                    |
| ------------- | ------- | ------------------------------------------------------------------------ |
| Pool / Swiss  | 75 min  | 60 min when a 2-day event must fit 6 pool rounds into day 1 (sectionals) |
| Cross-pool    | 75 min  | same as pools                                                            |
| Bracket       | 75 min  | semis and finals 90 min; flagship nationals used 100 min throughout      |
| Position pool | 75 min  | mirrors pool duration                                                    |

**Slot spacing:** start-to-start = duration + 10–15 minutes. 75-minute games on 90-minute slots is
the single most common grid in production (80+ observed rounds); 60-minute games sit on 70–75.

**Day window:** first pull 06:00–07:30, mode 07:00 (06:00–06:30 for hot season or a heavy slate).
Last game ends 17:15–18:30. A 09:00 start is unusual — use 07:00 unless staff say otherwise, and
never schedule past about 18:30 without confirming lights.

**Lunch:** roughly half of full days take a 60–90 minute midday break with no starts around
12:30–14:30; the rest run straight through on the buffers. Take the break when the slate fits
comfortably, drop it when a 2-day event needs 6+ rounds in a day.

**Rest:** minimum same-day gap between one team's games is 60 minutes after the previous game ends
(per-event minima cluster 60–75; the overall median gap is 105). Never go below 30.

**Team load:** pools day about 3 games per team (4 only with 60-minute slots); middle day 2–3;
finals day 1–2. Never more than 4 in a day.

**Fields:** `Field 1..N` unless staff use venue names. 2–4 fields is typical. 4–8 matches per field
per day is the healthy band; more than 9 on grass is an overpacked red flag. Rename with
`propose_update_field`; delete a spare unused field with `propose_delete_field` (refused if any
match still sits on it).

## Multi-day packing

| Days | Day 1                                              | Day 2                                              | Day 3                                                   |
| ---- | -------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------- |
| 2    | all pool rounds (evening CP if pools finish early) | CP first thing → brackets → placement/finals       | —                                                       |
| 3    | all pool rounds                                    | CP in the morning → opening brackets (QF, 9-16 R1) | remaining brackets + position pools; finals 14:30–16:30 |

Brackets never start before their feeding pools or cross-pool are complete. Finals go last, often on
a marquee field, with the day tapering — fewer matches, later starts.

## Using the scheduler

Do not schedule until `list_fields` returns at least one field and `list_stages` shows pools or
Swiss. If fields are missing, ask and propose fields; stop. One schedule proposal per turn.

`propose_recommended_schedule` is the default for placing a grid — reach for it first, and use
`propose_bulk_schedule` only when the recommender cannot place everything or when stages genuinely
need different durations. It places every match that has no time or no field, applying **one
duration to all of them**. Default first pull is **07:00**. It respects rest even before the
tournament starts (it falls back to seed numbers when teams are not yet assigned), and it will not
start a later stage until every match of the stage that feeds it has **ended** — a semi cannot
share a timeslot with a still-running pool, even on another field. If it cannot place every match,
it returns an error instead of a proposal — relax duration, add a field, extend the day, or build
the grid with one `propose_bulk_schedule`. Do not retry it two more times with slightly different
arguments; that stacks overlapping Confirm cards.

- Pass `end_date` for a multi-day event. Day 1 is pools; day 2 is cross-pool then brackets.
- `slot_buffer_mins` defaults to 15, which gives the standard 90-minute grid for 75-minute games.
  Set it to 0 only if staff explicitly want back-to-back slots.
- Because it is one duration per run, schedule **stage by stage** whenever durations differ, but
  put every assignment into **one** `propose_bulk_schedule` so staff see a single card:

1. Pools on day 1 at 75 minutes, later stages on day 2 at 90 if needed — one bulk proposal, not
   three recommended-schedule calls. This is the multi-duration case only; a single uniform
   duration is still one `propose_recommended_schedule`.
2. Fix individual slots with `propose_update_match`.
3. **Verify with `check_schedule_conflicts`** and report what it says: field overlaps, teams playing
   twice at once, rest below the minimum, stages out of order, anything finishing after the window.

If the scheduler reports matches it could not place, say so and offer the trade — shorter games, an
earlier start, another field, or spilling into the next morning. Never quietly drop them.

## Worked example

**"16 mixed teams this weekend on 3 fields — set it up and schedule it."** 16 teams means 24 pool
matches: 8 rounds on 3 fields, which at 90-minute slots runs 07:00 to 19:00. That does not fit, so
this is one of the cases worth asking about — 60-minute pool games, or extend pools into Sunday
morning? Then: day 1 pools, day 2 cross-pool at 07:00 followed by brackets on longer slots, finals
around 15:30. Summarise per-team load, rest minima and per-field counts so staff can sanity-check
before confirming.

## Anti-patterns

- Brackets or cross-pool scheduled before the feeding stage's last match ends.
- More than 4 games per team per day, or same-day gaps under 60 minutes.
- More than 9 matches on one field in a day, or uneven fields — one idle while another is packed.
- Starting a full slate at 09:00, which loses two rounds against the 07:00 norm.
- Running past 18:30 without confirming lights.
- Proposing schedule changes for completed matches.
- Reporting a schedule as clean without running `check_schedule_conflicts`.
