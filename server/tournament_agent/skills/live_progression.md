---
name: live_progression
status: active
always: false
priority: 20
when_phase: [live]
triggers:
  [
    score,
    result,
    won,
    beat,
    advance,
    next round,
    fixtures,
    standings,
    who makes,
    top 8,
    bracket,
    upset,
    seed swap,
    bye,
    swiss,
    forfeit,
    walkover,
    rank,
    tiebreak
  ]
requires_tools:
  [
    propose_match_score,
    get_swiss_standings,
    list_stages,
    get_standings,
    list_matches,
    list_brackets,
    propose_generate_fixtures
  ]
---

# Live progression skill

Running the event once it is LIVE: recording results, advancing stages, and answering the
standings questions staff get asked between rounds.

## The round loop

1. **Record.** `propose_match_score(match_id, score_team_1, score_team_2)`. One proposal per game.
2. **Confirm applies everything.** On Confirm the score is written, the match goes COMPLETED, pool
   or Swiss standings recompute with the WFDF tie-break procedure, `current_seeding` updates, any
   bracket/cross-pool seed swap is applied, and the next stage's placeholders are filled
   automatically. **Do not also propose `propose_generate_fixtures`** — it already ran.
3. **Verify.** `list_stages` to see which stages just completed and what filled.
4. **Schedule what appeared.** Newly filled bracket/CP/position-pool matches are created YTF; if
   they have no time yet, propose slots.

`propose_generate_fixtures` is only for repair: staff changed something in Classic, or a stage looks
stuck with empty placeholders after its feeder completed.

## Reading the state (pick the narrow tool)

| Question                              | Tool                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| Which stages are done, which are next | `list_stages`                                                                        |
| Pool / position-pool table            | `get_standings`                                                                      |
| Swiss table, byes, current round      | `get_swiss_standings`                                                                |
| Bracket as it stands now              | `list_brackets` (`current_seeding` is live, `initial_seeding` is the entry snapshot) |
| Who plays where next                  | `list_matches(stage=…, status=…, day=…, team_id=…)`                                  |

Never answer a standings question from the chat history. Read first — a score may have landed since.

## The two reseed rules (state which one applies)

- **Pools and position pools reseed inside their own seed set.** A pool holding seeds {2, 8, 10, 16}
  distributes exactly those four seeds by finish order — its winner takes seed 2, runner-up 8, and so
  on. Finishing first in a weak pool does not make a team the 1 seed.
- **Brackets and cross-pool swap on an upset.** When the lower seed wins, the two seeds trade places
  in `current_seeding`. Nothing else moves.

When you report a result, say which rule fired and what moved: "Pool B is complete — its seeds
2/8/10/16 now sit in finish order, so seed 2 is now <team>." Do not describe teams as "moving up the
overall standings" — that is not how this system ranks.

## Tie-breaks

Pool and position pool follow the WFDF championship appendix, exactly as written in the tournament
rules document:

1. games won in the pool (this is what makes a tie a tie)
2. games won counting only games between the tied teams
3. points difference counting only games between the tied teams
4. points difference counting all pool games
5. points scored counting only games between the tied teams
6. points scored counting all pool games
7. longest throw, one player per team

Whenever a criterion splits the group, the procedure **restarts at the top** within each sub-group
that is still tied, with head-to-head recomputed among only those teams.

Criteria 1–6 are computed for you. **Criterion 7 is not** — it is a physical tiebreak played on the
field. If teams are still level after points scored, the standings keep their existing order and
staff have to run a longest-throw. Say that plainly rather than presenting the order as settled.

Swiss is different and is **not** covered by the rules document: teams are grouped by points (2 per
win, 1 per draw), then separated by head-to-head wins → strength of opponents faced (the sum of
opponents' points) → overall points difference, with the same restart rule.

Read the tables, then name the criterion that actually separated the teams — "B is above C on
head-to-head" — rather than just asserting an order.

## Swiss specifics

- A group carries `current_round` and `num_rounds`. Pairings for round N+1 are generated when every
  game in round N is COMPLETED.
- Odd team counts get a bye each round: the lowest-ranked team that has not had one yet, credited
  with a win and 15 goals for. Byes are visible in `get_swiss_standings`; mention the bye team when
  reporting a round, because it moves the table without playing.
- Swiss feeds cross-pool or brackets exactly like pools do, once all rounds are complete.

## Forfeits and walkovers

There is no walkover status. A forfeit is recorded as a score:
`propose_match_score(match_id, 15, 0, forfeit=True)` in favour of the team that showed up. Say in
your summary that it is a forfeit and that it counts as a normal result for standings and
tie-breaks — because it does. If a team withdraws with several games left, propose the forfeits one
at a time and never touch team membership.

## "Who makes Top 8?" and other what-ifs

- If every feeding stage is complete, this is a **read**: `get_standings` / `get_swiss_standings`,
  then name the teams by seed band. No proposal.
- If games are outstanding, say which ones decide it and what each outcome would mean, working from
  the current table. Be explicit that it is conditional.
- **Never propose anything in an analysis turn.** A question is not a request to act — do not answer
  "who makes Top 8?" with a schedule proposal.

## Anti-patterns

- Proposing `propose_generate_fixtures` after every score (redundant — the score already ran it).
- Answering "who's in the bracket" from `initial_seeding` instead of `current_seeding`.
- Re-proposing a score for a match that is already COMPLETED — scores accumulate, so this
  double-counts and cannot be undone.
- Rescheduling a COMPLETED match when staff say "move the 11:00 game" — check status first.
- Describing pool reseeding as a global ranking.
- Reporting a Swiss round without mentioning the bye.
