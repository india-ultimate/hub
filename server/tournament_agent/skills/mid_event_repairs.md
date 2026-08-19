---
name: mid_event_repairs
status: active
always: false
priority: 25
when_status: [SCH, LIV]
triggers:
  [delay, rain, lightning, weather, waterlogged, field down, field lost, move, shift,
   swap, reschedule, push back, wrong, fix, mistake, rebuild, redo, withdraw, drop out,
   finals field, broadcast]
requires_tools:
  [check_schedule_conflicts, propose_shift_schedule, propose_delete_stage, list_matches,
   list_fields, list_stages, propose_update_match, propose_bulk_schedule]
---

# Mid-event repairs skill

Fixing a tournament that is already scheduled or already running. Repairs are surgery, not
redesign — the correct fix is almost always the smallest one that restores a legal schedule.

## Triage order (follow it every time)

1. **Scope it.** Which matches are actually affected — one match, one field, one day, or everything
   after a time? Read `list_matches` filtered as narrowly as the request allows.
2. **Freeze what is done.** Any COMPLETED match is out of scope, permanently. Exclude it from every
   proposal and say how many you excluded.
3. **Measure.** `check_schedule_conflicts` before you propose. It tells you what is already broken so
   you do not get blamed for it, and gives you the baseline to compare against.
4. **Propose the smallest change** that fixes it.
5. **Verify.** `check_schedule_conflicts` again after, and report the delta: field clashes, rest
   violations, matches pushed past the day window, anything left unplaced.

Never re-run the whole scheduler to fix one match. `propose_recommended_schedule` only places
matches with no time yet — on a live event it will look like it did nothing, or it will fill gaps
you deliberately left.

## Weather delay

"Lightning hold, push everything back 45 minutes."

`propose_shift_schedule(shift_mins=45, scope="from_time", from_time="<now or the hold time>")`.

- COMPLETED and in-progress matches are excluded automatically; state the count.
- Check the tail: if the last game now ends after about 18:30 there are no lights. Before proposing a
  shift that runs late, `ask_user`: shorten the remaining games, drop a placement round, or play into
  the next morning.
- Rest minimums usually survive a uniform shift because every game moves together. Verify anyway —
  a partial shift (only one field, only one stage) breaks rest silently.
- If the hold is long enough that the day cannot be recovered, do not propose a heroic 20-minute-slot
  grid. Ask which games staff want to protect: finals, or everyone's game count.

## Field lost

"Field 2 is waterlogged for the rest of the day."

`list_matches(day=…)` to see what is on it, then `propose_bulk_schedule` moving those matches onto
the remaining fields' free slots.

- Work from `check_schedule_conflicts` output so you do not move a match into a slot that is
  already taken.
- Report anything you could not place rather than quietly dropping it, and offer the trade: later
  finish, shorter games, or one round cut.
- There is no "unavailable" flag on a field. The durable fix is to leave it empty and pass
  `field_ids` explicitly when scheduling later stages.

## Moving one match, and swapping two

- One match to an empty slot: `propose_update_match(match_id, time=…, field_id=…)`.
- Two matches exchanging slots: **one field cannot hold two matches at the same start time**, so
  two separate proposals collide — whichever is confirmed first lands on the other's slot. Put both
  moves in a single `propose_bulk_schedule`, routing one of them via a free slot.
- Finals to the marquee field: `list_fields` shows which field is broadcast. Move whatever holds
  that slot first, in the same bulk proposal.

## Seeding mistakes

- **Before the tournament starts**, `propose_update_seeding` is the right fix and it is safe: it
  rewrites the tournament seeding *and* resyncs every pool and Swiss group's snapshot to match. You
  do not need to rebuild stages for a re-seed.
- **After the tournament starts**, seeding cannot be edited — the Confirm is rejected. Say so, and
  explain that mid-event seeds move only through results. If a pool genuinely holds the wrong teams,
  that is a rebuild (below), not a re-seed.

## Rebuilding a stage

`propose_delete_stage(kind, stage_id)` removes the stage and its matches together.

Only propose it when:
- no match in that stage is COMPLETED, and
- nothing downstream has already been seeded from it, and
- for pools and Swiss groups, the tournament has not started.

State the match count in your summary — staff are confirming the loss of those matches too. After
the delete is confirmed, propose the replacement stage in the same shape as the original
(pool/Swiss seeds, bracket seed range) and re-schedule the new matches; they are created with no
time.

If any of the three conditions fails, do not propose it. Say which condition blocks it and what the
narrower fix is.

## What you cannot repair

- **A score entered wrong.** Scores accumulate into standings and nothing reverses them. Django admin
  on the match, then Populate Fixtures from Classic Tournament Manager. Offer to show what the table
  should look like afterwards.
- **A team that needs to leave.** Forfeit their remaining games; never touch team membership.
- **A confirmed proposal.** There is no undo — only the next smallest forward change.

## Anti-patterns

- Rescheduling COMPLETED matches, including as collateral in a bulk shift.
- Two `propose_update_match` proposals that swap slots.
- Re-running the recommender on a live event to "clean up".
- Deleting a stage to fix a schedule problem.
- Proposing a repair without a before/after conflict check.
- Fixing the reported problem and silently changing three other games to make the grid tidier.
