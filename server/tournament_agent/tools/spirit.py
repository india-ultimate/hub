"""Roster lookup and spirit scoring.

The one corner of the tool surface that touches identified people, so it is also
the one that leans hardest on `privacy`: a name goes in, only ids come back, and
staff see names again via `{{player:<id>}}` tokens resolved on the way out.
"""

from __future__ import annotations

from typing import Any

from server.tournament.models import Match, Registration
from server.tournament_agent.tools.context import ToolContext, _safe, _team_map

SPIRIT_BLOCKS = {
    "team_1_received": "spirit_score_team_1",
    "team_2_received": "spirit_score_team_2",
    "team_1_self": "self_spirit_score_team_1",
    "team_2_self": "self_spirit_score_team_2",
}


def find_roster_player(ctx: ToolContext, team_id: int, query: str) -> dict[str, Any]:
    """Look a player up by name and get their id back. Names never come back out."""
    t = ctx.tournament
    if t.use_uc_registrations:
        return {
            "error": "This tournament uses Ultimate Central registrations, where player ids "
            "live in a different system. Pick the player in Classic Tournament Manager instead."
        }
    text = (query or "").strip().lower()
    if not text:
        return {"error": "query is required — pass the name staff gave you"}

    matches = [
        {
            "player_id": reg.player_id,
            "team_id": reg.team_id,
            "role": reg.role,
        }
        for reg in Registration.objects.filter(event=t.event, team_id=team_id).select_related(
            "player__user"
        )
        if text in f"{reg.player.user.get_full_name()} {reg.player.user.username}".lower()
    ]
    result: dict[str, Any] = {"matches": matches, "count": len(matches)}
    if len(matches) > 1:
        result["hint"] = (
            "More than one player matched. You cannot tell them apart from ids — ask_user "
            "with one option per id and the label '{{player:<id>}}', which staff see as a name."
        )
    elif not matches:
        result["hint"] = "Nobody on that team's roster matched. Check the team, or ask staff."
    return _safe(result)


def _spirit_row(score: Any) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "rules": score.rules,
        "fouls": score.fouls,
        "fair": score.fair,
        "positive": score.positive,
        "communication": score.communication,
        "total": score.total,
        "mvp_player_id": score.mvp_v2_id,
        "msp_player_id": score.msp_v2_id,
    }


def get_match_spirit(ctx: ToolContext, match_id: int) -> dict[str, Any]:
    match = Match.objects.select_related(
        *SPIRIT_BLOCKS.values(),
    ).get(id=match_id, tournament=ctx.tournament)
    return _safe(
        {
            "match_id": match.id,
            "team_1_id": match.team_1_id,
            "team_2_id": match.team_2_id,
            **{block: _spirit_row(getattr(match, attr)) for block, attr in SPIRIT_BLOCKS.items()},
        }
    )


def list_missing_spirit_scores(ctx: ToolContext) -> dict[str, Any]:
    """Played matches still missing spirit blocks — the chasing-captains list."""
    rows = []
    for match in (
        Match.objects.filter(tournament=ctx.tournament, status=Match.Status.COMPLETED)
        .select_related("team_1", "team_2", *SPIRIT_BLOCKS.values())
        .order_by("time", "id")
    ):
        missing = [block for block, attr in SPIRIT_BLOCKS.items() if getattr(match, attr) is None]
        if missing:
            rows.append(
                {
                    "match_id": match.id,
                    "match_name": match.name,
                    "team_1_name": match.team_1.name if match.team_1 else None,
                    "team_2_name": match.team_2.name if match.team_2 else None,
                    "missing": missing,
                }
            )
    return _safe({"matches": rows, "count": len(rows)})


def get_spirit_summary(ctx: ToolContext) -> dict[str, Any]:
    names = _team_map(ctx.tournament)
    return _safe(
        {
            "spirit_ranking": [
                {
                    "team_id": row.get("team_id"),
                    "team_name": names.get(int(row.get("team_id") or 0), ""),
                    "points": row.get("points"),
                    "self_points": row.get("self_points"),
                    "rank": row.get("rank"),
                }
                for row in (ctx.tournament.spirit_ranking or [])
            ]
        }
    )


def propose_spirit_scores(
    ctx: ToolContext,
    match_id: int,
    team_1_received: dict[str, Any] | None = None,
    team_2_received: dict[str, Any] | None = None,
    team_1_self: dict[str, Any] | None = None,
    team_2_self: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocks = {
        "team_1_received": team_1_received,
        "team_2_received": team_2_received,
        "team_1_self": team_1_self,
        "team_2_self": team_2_self,
    }
    given = {name: block for name, block in blocks.items() if block}
    if not given:
        return {"error": "Pass at least one spirit block"}
    return ctx.create_proposal(
        "propose_spirit_scores",
        f"Spirit scores for match {match_id}: {', '.join(sorted(given))}",
        {"match_id": match_id, **given},
    )
