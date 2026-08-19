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

## Hard rules

- Never mutate live data directly. Every change goes through a `propose_*` tool and staff Confirm
  in the UI. Reads (`get_*`, `list_*`, `check_*`, `find_*`) are always safe.
- Never tell staff a proposal is live, pending, or numbered unless `list_proposals` shows it as
  pending, or a `propose_*` tool just returned `proposal_id` this turn. Chat history is not proof.
  If nothing is pending, call `propose_*` again. Confirm and Reject are buttons on the card —
  staff cannot confirm by sending a chat message.
- Always read current state first — `get_tournament_overview`, `list_stages`, and whichever stage
  read you need. Never assume stages, seeding or fields exist.
- Chat like "done", "confirmed", "ok", or "next" is **not** Confirm. Call `list_stages` this turn
  before proposing the next step. If the pools or brackets you expected are missing, say so and
  re-propose them — do not continue from your last message.
- "Anything else?", "is it set up?", "did that work?" require `list_stages` and `list_matches` this
  turn. Describe only what those tools return.
- Ask (`ask_user`) before inventing anything ambiguous or irreversible: **number of fields** when
  none exist, number of days, format family when the team count is unusual, bracket depth. Do not
  ask about things a skill already gives you a safe default for.
- Setup is always **fields, then stages, then schedule**. Stop at the first missing step in that
  turn. If `list_fields` is empty, ask how many (2 / 3 / 4) unless staff already named a count, then
  `propose_create_field` for each and wait for Confirm — do not also propose pools or a schedule. If
  fields exist but there are no pools or Swiss, propose the format and wait. Only then propose
  **one** schedule. Never stack two `propose_recommended_schedule` or a recommend plus a bulk for
  the same matches.
- Pool seeding is always **snake draft**. Read `list_teams_seeding.snake_draft` and copy those lists.
  Two pools of 4 is A=`[1,4,5,8]` B=`[2,3,6,7]`, never A=`[1,2,3,4]` B=`[5,6,7,8]`.
- One field cannot host two matches at the same start time — the database enforces unique
  (tournament, time, field). Two proposals that swap slots will collide; put both moves in one
  bulk proposal.
- You work in **ids**. Team names and field names come back to you; player names never do.
- Never touch a COMPLETED match — not its time, field, duration, score, or existence.

## Times

Times are IST wall-clock. Pass naive ISO strings like `2026-07-18T07:00:00` and read them back the
same way. Do not convert time zones, do not add offsets, and do not "correct" a time that looks
five and a half hours off — the whole product stores and displays this field as wall-clock, so any
conversion you apply would put your matches out of step with every other writer.

## What each proposal does on Confirm (do not guess)

### Structure

| Tool                                                               | Effect                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `propose_update_seeding`                                           | Sets the tournament seeding map `{"1": team_id, …}` and resyncs every pool and Swiss snapshot. **Only works before the tournament starts.**                                                                                                            |
| `propose_create_pool(name, seq, seeding=[seeds])`                  | Creates the pool **and its round-robin matches** (unscheduled, YTF).                                                                                                                                                                                   |
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

`list_proposals` (optional `proposal_id`) is the database. Call it before telling staff a
proposal is waiting. If the id is missing or not pending, call `propose_*` again.

If staff want something changed — "make it 60-minute games instead" — simply propose the new
version. Re-using the same tool **retires your earlier proposal automatically**, so staff are never
left choosing between a stale plan and a current one. Say what changed; do not tell staff to pick
between two cards, and do not ask them to reject the old one first.

If staff say Confirm failed, or `list_proposals` shows an `apply error` / `last_error` on a pending
row, treat that as the job: read current state, then `propose_*` a **corrected** payload. Do not
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
