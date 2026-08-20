"""Read tools: what the agent is allowed to look at.

None of these write. `services.agent` derives its read-only set from the handler
registry rather than a list kept here, so a read added below is picked up on its own.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Q

from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    Pool,
    PositionPool,
    SwissRound,
    TournamentField,
)
from server.tournament_agent.domain.format import snake_draft_options
from server.tournament_agent.models import AgentProposal, ProposalStatus
from server.tournament_agent.tools.context import ToolContext, _safe, _team_map
from server.tournament_agent.tools.queries import (
    STAGE_FIELDS,
    STAGE_MODELS,
    _match_row,
    match_queryset,
)


def get_tournament_overview(ctx: ToolContext) -> dict[str, Any]:
    t = ctx.tournament
    event = t.event
    matches = Match.objects.filter(tournament=t)
    return _safe(
        {
            "tournament_id": t.id,
            "title": event.title,
            "slug": event.slug or "",
            "status": t.status,
            "team_count": t.teams.count(),
            "pool_count": Pool.objects.filter(tournament=t).count(),
            "swiss_count": SwissRound.objects.filter(tournament=t).count(),
            "bracket_count": Bracket.objects.filter(tournament=t).count(),
            "cross_pool_count": CrossPool.objects.filter(tournament=t).count(),
            "position_pool_count": PositionPool.objects.filter(tournament=t).count(),
            "field_count": TournamentField.objects.filter(tournament=t).count(),
            "match_count": matches.count(),
            "unscheduled_match_count": matches.filter(
                Q(time__isnull=True) | Q(field__isnull=True)
            ).count(),
            "pending_proposal_count": AgentProposal.objects.filter(
                session=ctx.session, status=ProposalStatus.PENDING
            ).count(),
            "start_date": str(event.start_date),
            "end_date": str(event.end_date),
        }
    )


def list_teams_seeding(ctx: ToolContext) -> dict[str, Any]:
    t = ctx.tournament
    names = _team_map(t)
    seeding = []
    for seed_str, team_id in sorted((t.initial_seeding or {}).items(), key=lambda x: int(x[0])):
        tid = int(team_id)
        seeding.append({"seed": int(seed_str), "team_id": tid, "team_name": names.get(tid, "")})
    n = len(seeding) or t.teams.count()
    return _safe(
        {
            "seeding": seeding,
            "snake_draft": snake_draft_options(n),
            "pool_seeding_rule": (
                "Assign pools from snake_draft, never sequential blocks like 1-4 vs 5-8. "
                "Two pools of 4 is A=[1,4,5,8] B=[2,3,6,7]."
            ),
        }
    )


def list_pools(ctx: ToolContext) -> dict[str, Any]:
    names = _team_map(ctx.tournament)
    pools = []
    for pool in Pool.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        seeds = []
        for seed, team_id in sorted((pool.initial_seeding or {}).items(), key=lambda x: int(x[0])):
            tid = int(team_id)
            seeds.append({"seed": int(seed), "team_id": tid, "team_name": names.get(tid, "")})
        standings = []
        for team_id, row in (pool.results or {}).items():
            tid = int(team_id)
            standings.append(
                {
                    "team_id": tid,
                    "team_name": names.get(tid, ""),
                    "rank": row.get("rank"),
                    "wins": row.get("wins"),
                    "losses": row.get("losses"),
                    "draws": row.get("draws"),
                    "GF": row.get("GF"),
                    "GA": row.get("GA"),
                }
            )
        pools.append(
            {
                "id": pool.id,
                "name": pool.name,
                "sequence_number": pool.sequence_number,
                "seeding": seeds,
                "standings": standings,
            }
        )
    return _safe({"pools": pools})


def list_swiss_rounds(ctx: ToolContext) -> dict[str, Any]:
    rounds = []
    for sw in SwissRound.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        rounds.append(
            {
                "id": sw.id,
                "name": sw.name,
                "sequence_number": sw.sequence_number,
                "num_rounds": sw.num_rounds,
                "current_round": sw.current_round,
                "initial_seeding": sw.initial_seeding,
            }
        )
    return _safe({"swiss_rounds": rounds})


def list_brackets(ctx: ToolContext) -> dict[str, Any]:
    brackets = []
    for b in Bracket.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        brackets.append(
            {
                "id": b.id,
                "name": b.name,
                "sequence_number": b.sequence_number,
                "initial_seeding": b.initial_seeding,
                "current_seeding": b.current_seeding,
            }
        )
    return _safe({"brackets": brackets})


def list_cross_pools(ctx: ToolContext) -> dict[str, Any]:
    items = []
    for cp in CrossPool.objects.filter(tournament=ctx.tournament):
        items.append(
            {
                "id": cp.id,
                "initial_seeding": cp.initial_seeding,
                "current_seeding": cp.current_seeding,
            }
        )
    return _safe({"cross_pools": items})


def list_position_pools(ctx: ToolContext) -> dict[str, Any]:
    items = []
    for pp in PositionPool.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        items.append(
            {
                "id": pp.id,
                "name": pp.name,
                "sequence_number": pp.sequence_number,
                "initial_seeding": pp.initial_seeding,
            }
        )
    return _safe({"position_pools": items})


def list_fields(ctx: ToolContext) -> dict[str, Any]:
    fields = [
        {
            "id": f.id,
            "name": f.name,
            "address": f.address,
            "is_broadcasted": f.is_broadcasted,
        }
        for f in TournamentField.objects.filter(tournament=ctx.tournament).order_by("name")
    ]
    return _safe({"fields": fields})


# Stage kind -> the Match FK naming it, and the model behind it. One list, so the
# kinds the tool schemas advertise, the ones reads bucket by, and the ones the
# apply path accepts cannot drift apart.


def list_matches(
    ctx: ToolContext,
    unscheduled_only: bool = False,
    stage: str | None = None,
    status: str | None = None,
    day: str | None = None,
    team_id: int | None = None,
) -> dict[str, Any]:
    qs = match_queryset(ctx.tournament)
    if unscheduled_only:
        qs = qs.filter(Q(time__isnull=True) | Q(field__isnull=True))
    if stage in STAGE_FIELDS:
        qs = qs.exclude(**{f"{STAGE_FIELDS[stage]}__isnull": True})
    if status:
        qs = qs.filter(status=status)
    if day:
        qs = qs.filter(time__date=day)
    if team_id:
        qs = qs.filter(Q(team_1_id=team_id) | Q(team_2_id=team_id))

    matches = [_match_row(m) for m in qs.order_by("time", "id")]
    return _safe({"matches": matches, "count": len(matches)})


def _proposal_row(proposal: AgentProposal) -> dict[str, Any]:
    row = {
        "id": proposal.id,
        "tool_name": proposal.tool_name,
        "summary": proposal.summary,
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
    }
    if proposal.last_error:
        row["last_error"] = proposal.last_error
        row["note"] = (
            "Staff tried to Confirm this and it failed. Call the matching "
            "propose_* tool with a corrected payload — do not reuse this one."
        )
    return row


def list_proposals(ctx: ToolContext, proposal_id: int | None = None) -> dict[str, Any]:
    """What staff can actually Confirm. Chat that names an id is not proof it exists."""
    pending = [
        _proposal_row(row)
        for row in ctx.session.proposals.filter(status=ProposalStatus.PENDING).order_by(
            "created_at"
        )
    ]
    result: dict[str, Any] = {
        "pending": pending,
        "count": len(pending),
        "note": (
            "Only these pending proposals have a Confirm button. "
            "If this list is empty, nothing is waiting — call propose_* again."
        ),
    }
    if proposal_id is not None:
        row = ctx.session.proposals.filter(id=proposal_id).first()
        if row is None:
            result["lookup"] = {
                "id": proposal_id,
                "found": False,
                "message": (
                    f"No proposal #{proposal_id} on this session. Do not tell staff it "
                    "is pending. If they still want the change, call propose_*."
                ),
            }
        else:
            lookup: dict[str, Any] = {"found": True, **_proposal_row(row)}
            if row.status != ProposalStatus.PENDING:
                lookup["message"] = (
                    f"Proposal #{proposal_id} is {row.status}, not pending. "
                    "Staff have no Confirm button for it. Propose again if the "
                    "change is still needed."
                )
            result["lookup"] = lookup
    return _safe(result)


def list_stages(ctx: ToolContext) -> dict[str, Any]:
    """Every stage with its completion state — the cheap 'where are we?' read.

    The agent is told to call this first on most turns, so the match side is one
    grouped pass rather than four aggregates and a row fetch per stage.
    """
    t = ctx.tournament
    tallies: dict[tuple[str, int], dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "completed": 0, "unscheduled": 0, "times": []}
    )
    for row in Match.objects.filter(tournament=t).values(
        "status", "time", "field_id", *(f"{field}_id" for field in STAGE_FIELDS.values())
    ):
        stage = next(
            (s for s, field in STAGE_FIELDS.items() if row[f"{field}_id"]),
            None,
        )
        if stage is None:
            continue
        tally = tallies[(stage, row[f"{STAGE_FIELDS[stage]}_id"])]
        tally["total"] += 1
        if row["status"] == Match.Status.COMPLETED:
            tally["completed"] += 1
        if row["time"] is None or row["field_id"] is None:
            tally["unscheduled"] += 1
        if row["time"]:
            tally["times"].append(row["time"])

    empty: dict[str, Any] = {"total": 0, "completed": 0, "unscheduled": 0, "times": []}
    stages = []
    for stage, model in STAGE_MODELS.items():
        rows = model.objects.filter(tournament=t)
        if stage != "cross_pool":
            rows = rows.order_by("sequence_number")
        for row in rows:
            tally = tallies.get((stage, row.id), empty)
            times = tally["times"]
            stages.append(
                {
                    "stage": stage,
                    "id": row.id,
                    "name": getattr(row, "name", "Cross Pool"),
                    "sequence_number": getattr(row, "sequence_number", 1),
                    "match_count": tally["total"],
                    "completed_count": tally["completed"],
                    "is_complete": tally["total"] > 0 and tally["completed"] == tally["total"],
                    "unscheduled_count": tally["unscheduled"],
                    "first_match_time": min(times).isoformat() if times else None,
                    "last_match_time": max(times).isoformat() if times else None,
                }
            )
    return _safe({"tournament_status": t.status, "stages": stages})


def _named_seeding(names: dict[int, str], seeding: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for seed, team_id in sorted((seeding or {}).items(), key=lambda x: int(x[0])):
        tid = int(team_id)
        rows.append({"seed": int(seed), "team_id": tid, "team_name": names.get(tid, "")})
    return rows


def get_swiss_standings(ctx: ToolContext) -> dict[str, Any]:
    names = _team_map(ctx.tournament)
    groups = []
    for sw in SwissRound.objects.filter(tournament=ctx.tournament).order_by("sequence_number"):
        standings = []
        for team_id, row in (sw.results or {}).items():
            tid = int(team_id)
            wins, draws = row.get("wins", 0), row.get("draws", 0)
            standings.append(
                {
                    "team_id": tid,
                    "team_name": names.get(tid, ""),
                    "rank": row.get("rank"),
                    "points": wins * 2 + draws,
                    "wins": wins,
                    "losses": row.get("losses"),
                    "draws": draws,
                    "GF": row.get("GF"),
                    "GA": row.get("GA"),
                    "opp_strength": row.get("opp_strength"),
                }
            )
        standings.sort(key=lambda r: (r["rank"] is None, r["rank"]))
        groups.append(
            {
                "id": sw.id,
                "name": sw.name,
                "current_round": sw.current_round,
                "num_rounds": sw.num_rounds,
                # A bye moves the table without a match being played, so it has to
                # be visible when reporting a round.
                "byes": {rnd: names.get(int(tid), "") for rnd, tid in (sw.byes or {}).items()},
                "standings": standings,
            }
        )
    return _safe({"swiss_rounds": groups})


def get_standings(ctx: ToolContext) -> dict[str, Any]:
    t = ctx.tournament
    names = _team_map(t)
    position_pools = []
    for pp in PositionPool.objects.filter(tournament=t).order_by("sequence_number"):
        position_pools.append(
            {
                "id": pp.id,
                "name": pp.name,
                "standings": [
                    {
                        "team_id": int(team_id),
                        "team_name": names.get(int(team_id), ""),
                        **{k: row.get(k) for k in ("rank", "wins", "losses", "draws", "GF", "GA")},
                    }
                    for team_id, row in (pp.results or {}).items()
                ],
            }
        )
    return _safe(
        {
            "pools": list_pools(ctx)["pools"],
            "swiss_rounds": get_swiss_standings(ctx)["swiss_rounds"],
            "position_pools": position_pools,
            "brackets": [
                {
                    "id": b.id,
                    "name": b.name,
                    "current_seeding": _named_seeding(names, b.current_seeding),
                }
                for b in Bracket.objects.filter(tournament=t).order_by("sequence_number")
            ],
            "current_seeding": _named_seeding(names, t.current_seeding),
        }
    )


def check_schedule_conflicts(
    ctx: ToolContext, min_rest_mins: int = 60, day_end_hour: int = 18, day: str | None = None
) -> dict[str, Any]:
    from server.tournament_agent.domain.validate import schedule_conflicts

    return _safe(
        schedule_conflicts(
            ctx.tournament, min_rest_mins=min_rest_mins, day_end_hour=day_end_hour, day=day
        )
    )
