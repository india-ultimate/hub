---
name: spirit_and_roster
status: active
always: false
priority: 30
# Deliberately trigger-only: spirit is a narrow task, and loading it on every live
# turn would cost ~5k characters on turns that never mention it.
when_status: []
triggers:
  [
    spirit,
    sotg,
    mvp,
    msp,
    most valuable,
    most spirited,
    roster,
    player,
    nominate,
    spirit score,
    spirit ranking
  ]
requires_tools:
  [
    find_roster_player,
    get_match_spirit,
    list_missing_spirit_scores,
    get_spirit_summary,
    propose_spirit_scores,
    ask_user,
    list_matches
  ]
---

# Spirit and roster skill

Recording spirit scores, and finding the player behind a name staff typed.

## You work in ids, staff read names

The system never hands you a person's name, email or phone. You get **player ids**.
`find_roster_player(team_id, query)` takes the name staff wrote and gives you back ids only.

When you need to show a person to staff — in an `ask_user` option label, a proposal summary, or
your reply — write `{{player:<id>}}`. The interface turns that into the real name. Never guess a
name, and never repeat one back as though the system gave it to you.

If more than one roster entry matches, you cannot tell them apart from ids. Ask:

> `ask_user("Which player did you mean?", options=[{id: "812", label: "{{player:812}}"},

           {id: "907", label: "{{player:907}}"}])`

## Which block is which

A match holds four spirit blocks. Getting these backwards is the easiest mistake here:

| Block             | Meaning                              |
| ----------------- | ------------------------------------ |
| `team_1_received` | what team 1 **was given**, by team 2 |
| `team_2_received` | what team 2 **was given**, by team 1 |
| `team_1_self`     | team 1 rating **itself**             |
| `team_2_self`     | team 2 rating **itself**             |

MVP and MSP live on the **received** blocks only, and the nominated player must be on **that same
team's** roster — `team_1_received.mvp_id` is a team 1 player, chosen by team 2. Self blocks carry
no MVP/MSP; a proposal that puts one there is rejected.

## Scores

Five components — `rules`, `fouls`, `fair`, `positive`, `communication` — each **0 to 4**. The
total is computed for you; never send it. Anything outside 0–4 is rejected, because the database
would accept it and quietly skew the whole ranking.

`comments` is optional free text, up to 500 characters. You can write staff's comment in, but you
will never read comments back — they are not returned by any tool.

## Enter all four blocks or the ranking will not move

The tournament spirit ranking counts a match for a team **only when both** that team's received and
self blocks exist. Enter three of the four and nothing changes in the table, with no error anywhere.
The proposal result tells you which teams actually counted — report that, and say plainly when a
team is still not counted.

## Worked sequence

Staff: _"Match 42 — Alpha gave Beta 2/2/3/2/2 and rated themselves 2/2/2/2/2, MVP for Beta was
Priya."_

1. `get_match_spirit(42)` — confirm which side is team 1, and what is already recorded.
2. `find_roster_player(team_id=<Beta's id>, query="Priya")` → one id, say 812.
3. `propose_spirit_scores(match_id=42, team_2_received={rules:2, fouls:2, fair:3, positive:2,
communication:2, mvp_id:812}, team_1_self={rules:2, fouls:2, fair:2, positive:2,
communication:2})`.
4. In your summary: name the MVP as `{{player:812}}`, and say Beta is not yet counted towards the
   ranking because its self score is missing.

## Chasing what is missing

`list_missing_spirit_scores()` gives every played match still short a block, with team names. That
is the list staff actually want at the end of a day — offer it rather than making them ask per
match. `get_spirit_summary()` is the ranking as it stands.

## Anti-patterns

- Putting a received score in a self block, or an MVP on a self block.
- Nominating a player from the other team, or from another team entirely.
- Sending `total`.
- Reporting "spirit recorded" when only one side was entered — the ranking did not move.
- Repeating a player's name as if the system supplied it; use `{{player:<id>}}`.
- Asking staff for spirit scores they did not mention. If they gave you one block, propose that one.
