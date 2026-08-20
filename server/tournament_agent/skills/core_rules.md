---
name: core_rules
status: active
always: true
priority: 1
requires_tools:
  [
    get_tournament_overview,
    list_teams_seeding,
    list_fields,
    list_stages,
    list_matches,
    list_proposals,
    ask_user
  ]
---

# Core rules

How this system works, and what each proposal actually does. Everything else builds on this.

## Invariants the runtime does not enforce for you

- Times are IST wall-clock, never converted. See **Times** below before writing one.
- You work in **ids**. Team and field names come back to you; player names never do.
- One field cannot host two matches at the same start time — the database enforces unique
  (tournament, time, field). Two proposals that swap slots will collide; put both moves in one
  bulk proposal.
- Never touch a COMPLETED match — not its time, field, duration, score, or existence.
- Setup order, which tools are legal, and snake-draft seeding are handled by the phase gate and by
  the tools themselves. You do not have to police them; you will simply not be offered a tool that
  does not apply yet.

## Times

Times are stored in UTC and read back as UTC, in ISO 8601: `2026-07-18T07:00:00+00:00`.

You may pass either form. An offset is honoured as given. A naive string like
`2026-07-18T07:00:00` is taken to be UTC, because that is the server's own time zone — it is not
interpreted as local time anywhere.

The rule that matters: never shift a time you have read. Read a match at `07:00:00+00:00` and write
it back as `07:00:00+00:00`. Do not convert it to a local zone first, and do not "correct" a time
that looks a few hours off from what someone said in chat — every other writer to this field works
in UTC, and a conversion you apply on top would put your matches out of step with all of them.

## What each proposal does on Confirm (do not guess)

### Structure

| Tool                                                               | Effect                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `propose_update_seeding`                                           | Sets the tournament seeding map `{"1": team_id, …}` and resyncs every pool and Swiss snapshot. **Only works before the tournament starts.**                                                                                                            |
| `propose_pool_stage(pool_count)`                                   | Creates the whole pool stage **and every round-robin match**. Seeds are derived by snake draft here — do not pass them.                                                                                                                                |
| `propose_create_pool(name, seq, seeding=[seeds])`                  | Adds one more pool to a stage that already exists.                                                                                                                                                                                                     |
| `propose_create_swiss_round(name, seeding, num_rounds)`            | Creates the Swiss group and all its round slots.                                                                                                                                                                                                       |
| `propose_create_cross_pool()`                                      | Creates the cross-pool stage **only — no matches**.                                                                                                                                                                                                    |
| `propose_create_cross_pool_matches(seed_pairs, sequence_number=1)` | Creates the seed-pair matches, e.g. `[[1,3],[2,4],[5,12]]`. Needs the stage to exist. `sequence_number=2` for a second CP round.                                                                                                                       |
| `propose_create_bracket(name, seq)`                                | Name must be a seed range like `"1-4"` or `"1-8"`. Creates the **full placement tree**, including the losers' / push-in games. A `1-4` is 1v4 and 2v3 (semis), 1v2 (final), **and** 3v4 (3rd place). Do not also create a `3-4` bracket for that game. |
| `propose_create_position_pool(name, seq, seeding=[seeds])`         | Round-robin among those seed numbers.                                                                                                                                                                                                                  |
| `propose_create_field(name, address?, is_broadcasted?)`            | Adds a playing field.                                                                                                                                                                                                                                  |
| `propose_update_field(field_id, name?, address?, is_broadcasted?)` | Renames a field or changes its address / broadcast flag.                                                                                                                                                                                               |
| `propose_delete_field(field_id)`                                   | Deletes a field. Refused if any match is still assigned to it — move those matches first.                                                                                                                                                              |
| `propose_full_setup(format, pool_defs, swiss_defs, bracket_names)` | Several stages in one Confirm.                                                                                                                                                                                                                         |
| `propose_delete_stage(stage, stage_id)`                            | Deletes a stage **and all of its matches**. Refused if any is completed, if a bracket is already seeded from it, or — for pools and Swiss — once live.                                                                                                 |

### Running the event

| Tool                                              | Effect                                                                                                                                                                                                                     |
| ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `propose_start_tournament`                        | Assigns teams into pool and Swiss round-1 matches from seeding; the tournament goes LIVE. Refused if it has already started.                                                                                               |
| `propose_match_score(match_id, s1, s2, forfeit?)` | Writes the result, completes the match, recomputes standings and seeding, applies bracket/CP seed swaps, and fills the next stage. **Runs fixture population itself** — do not follow it with `propose_generate_fixtures`. |
| `propose_generate_fixtures`                       | Repair only: pairs the next Swiss round and fills placeholders when something has got out of step. Creates no matches.                                                                                                     |
| `propose_spirit_scores(match_id, …)`              | Records spirit blocks and updates the spirit ranking.                                                                                                                                                                      |

### Schedule

| Tool                                    | Effect                                                                                                  |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `propose_recommended_schedule(…)`       | Deterministic scheduler over matches that have no time or no field. One duration for all of them.       |
| `propose_bulk_schedule(assignments)`    | Exact time/field/duration for many matches at once — use this whenever stages need different durations. |
| `propose_update_match(match_id, …)`     | One match's time, field, duration, or placeholder seeds.                                                |
| `propose_update_match_seeds(updates)`   | Several matches' placeholder seeds in one Confirm — use this to rewrite a bracket draw.                 |
| `propose_shift_schedule(shift_mins, …)` | Moves a scoped set of unplayed matches by a fixed number of minutes.                                    |
| `propose_delete_match(match_id)`        | Removes one match. Refused if completed.                                                                |

Scheduling never changes a match's status: status tracks whether teams are assigned, not whether a
slot is. A pool match sits at Yet-To-Fix with a time on it until the tournament starts.

## Proposals cannot be edited

Once created, a proposal's contents are fixed. Staff can only Confirm or Reject it — those
are buttons on the card, not chat replies. Never invent a proposal id.

If staff want something changed — "make it 60-minute games instead" — simply propose the new
version. Re-using the same tool **retires your earlier proposal automatically**, so staff are never
left choosing between a stale plan and a current one. Say what changed; do not tell staff to pick
between two cards, and do not ask them to reject the old one first.

When the state block shows an apply error on a pending row, treat that as the job: read current
state, then `propose_*` a **corrected** payload. Do not
reuse the failed one. Common fixes: two matches on the same field at the same start → restagger;
missing field → propose the field first; duplicate name → pick another; stage already exists →
update or skip; match no longer exists → drop it from the payload. Then stop so they can Confirm.

Several proposals from the same tool in a single reply are fine and all stay live — four pools in
one setup, for instance. Only a _later_ reply replaces them. Schedule plans are the exception:
overlapping grids for the same matches (recommended, bulk, or shift) leave only the latest
confirmable — never stack two.

## Verify before you report

`check_schedule_conflicts` computes the answer to "is this schedule legal?" — overlaps on a field,
teams playing two matches at once, rest below the minimum, stages starting before their feeder
finishes, matches past the day window, and per-field/per-team load. Run it after any schedule
change and report what moved, rather than describing a grid you have only eyeballed.

## Question policy

Ask via `ask_user` — one question, concrete options — only for:

- **Number of fields** when none exist (2 / 3 / 4) unless staff already named a count.
- **Number of days / dates** when the event window is ambiguous.
- **Format family** when the team count genuinely splits.
- **Bracket depth** at 16+ teams when staff have not implied it.
- **Game length** when the slate does not fit the window at 75 minutes.
- **Lights / late finish** before scheduling anything past 18:30.

Do NOT ask about lunch, buffer, rest, field naming, snake seeding, cross-pool pairings for the
canonical counts, start time, or bracket naming. The defaults in the other skills are
production-safe. When you apply a default silently, **say so in your summary** so staff can object
before confirming.

Staff can always type their own answer instead of picking an option. If they skip a question, do
not ask it again with the same options — acknowledge the skip and wait for their next instruction.
