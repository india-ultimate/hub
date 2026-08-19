"""Proposal tools: everything the agent can ask staff to approve.

Nothing here writes to the tournament. Each returns a pending `AgentProposal`;
`services.proposals` is what applies one once staff hit Confirm. Validation that
can be done at propose time belongs here, so staff are never shown a plan that
will only fail on Confirm.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from server.tournament.models import Match
from server.tournament_agent.domain.validate import DEFAULT_MATCH_MINS
from server.tournament_agent.tools.context import ToolContext
from server.tournament_agent.tools.queries import STAGE_FIELDS, match_queryset


def propose_create_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_pool",
        f"Create pool {name} with seeds {seeding}",
        {"name": name, "sequence_number": sequence_number, "seeding": seeding},
    )


def propose_create_swiss_round(
    ctx: ToolContext, name: str, seeding: list[int], num_rounds: int, sequence_number: int = 1
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_swiss_round",
        f"Create Swiss group {name} ({num_rounds} rounds) with seeds {seeding}",
        {
            "name": name,
            "seeding": seeding,
            "num_rounds": num_rounds,
            "sequence_number": sequence_number,
        },
    )


def propose_create_cross_pool(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal("propose_create_cross_pool", "Create cross pool stage", {})


def propose_create_bracket(ctx: ToolContext, name: str, sequence_number: int) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_bracket",
        f"Create bracket {name}",
        {"name": name, "sequence_number": sequence_number},
    )


def propose_create_position_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_position_pool",
        f"Create position pool {name} with seeds {seeding}",
        {"name": name, "sequence_number": sequence_number, "seeding": seeding},
    )


def propose_create_field(
    ctx: ToolContext,
    name: str,
    address: str | None = None,
    is_broadcasted: bool = False,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_create_field",
        f"Create field '{name.strip()}'",
        {"name": name.strip(), "address": address, "is_broadcasted": is_broadcasted},
    )


def propose_create_cross_pool_matches(
    ctx: ToolContext, seed_pairs: list[list[int]], sequence_number: int = 1
) -> dict[str, Any]:
    pairs = [[int(pair[0]), int(pair[1])] for pair in seed_pairs]
    summary_pairs = ", ".join(f"{a} v {b}" for a, b in pairs)
    return ctx.create_proposal(
        "propose_create_cross_pool_matches",
        f"Create {len(pairs)} cross pool matches (round {sequence_number}): {summary_pairs}",
        {"seed_pairs": pairs, "sequence_number": sequence_number},
    )


def propose_update_seeding(ctx: ToolContext, seeding: dict[str, int]) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_update_seeding",
        "Update tournament seeding",
        {"seeding": seeding},
    )


def propose_update_match(
    ctx: ToolContext,
    match_id: int,
    time: str | None = None,
    field_id: int | None = None,
    duration_mins: int | None = None,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_update_match",
        f"Update match {match_id}",
        {
            "match_id": match_id,
            "time": time,
            "field_id": field_id,
            "duration_mins": duration_mins,
        },
    )


def propose_delete_match(ctx: ToolContext, match_id: int) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_delete_match",
        f"Delete match {match_id}",
        {"match_id": match_id},
    )


def propose_bulk_schedule(ctx: ToolContext, assignments: list[dict[str, Any]]) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_bulk_schedule",
        f"Schedule {len(assignments)} matches",
        {"assignments": assignments},
    )


def propose_match_score(
    ctx: ToolContext,
    match_id: int,
    score_team_1: int,
    score_team_2: int,
    forfeit: bool = False,
) -> dict[str, Any]:
    note = " (forfeit)" if forfeit else ""
    return ctx.create_proposal(
        "propose_match_score",
        f"Record match {match_id}: {score_team_1}-{score_team_2}{note}",
        {
            "match_id": match_id,
            "score_team_1": score_team_1,
            "score_team_2": score_team_2,
            "forfeit": bool(forfeit),
        },
    )


def propose_shift_schedule(
    ctx: ToolContext,
    shift_mins: int,
    from_time: str | None = None,
    day: str | None = None,
    field_id: int | None = None,
    match_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Move a set of not-yet-played matches by a fixed number of minutes."""
    from datetime import timedelta

    from django.utils.dateparse import parse_datetime

    scope = match_queryset(ctx.tournament).filter(time__isnull=False)
    if match_ids:
        scope = scope.filter(id__in=match_ids)
    if day:
        scope = scope.filter(time__date=day)
    if field_id:
        scope = scope.filter(field_id=field_id)
    if from_time:
        cutoff = parse_datetime(from_time)
        if cutoff is None:
            return {"error": f"Invalid from_time: {from_time}"}
        if timezone.is_naive(cutoff):
            cutoff = timezone.make_aware(cutoff)
        scope = scope.filter(time__gte=cutoff)

    matches = list(scope.exclude(status=Match.Status.COMPLETED).order_by("time", "id"))
    if not matches:
        return {"error": "No movable matches matched that scope (completed matches are excluded)"}

    delta = timedelta(minutes=shift_mins)
    moving = {m.id for m in matches}
    # Anything staying put still owns its slot, so a shift must not collide with it.
    # Slots are windows, not instants: landing part-way inside a match that is not
    # moving double-books the field just as surely as landing exactly on it.
    fixed_windows = [
        (m.field_id, m.time, m.time + timedelta(minutes=m.duration_mins or DEFAULT_MATCH_MINS))
        for m in match_queryset(ctx.tournament).filter(time__isnull=False, field__isnull=False)
        if m.id not in moving
    ]
    assignments = []
    for m in matches:
        new_time = m.time + delta
        new_end = new_time + timedelta(minutes=m.duration_mins or DEFAULT_MATCH_MINS)
        # A uniform shift keeps the moving matches the same distance apart, so only
        # the ones staying put can be collided with.
        if any(
            field == m.field_id and new_time < end and start < new_end
            for field, start, end in fixed_windows
        ):
            return {
                "error": f"Shifting by {shift_mins} min would put {m.name or m.id} on top of "
                "another match already in that slot — pick a different shift or scope"
            }
        assignments.append({"match_id": m.id, "time": new_time.isoformat(), "field_id": m.field_id})

    # Scoped to the same filters as the shift itself: a single-field shift must not
    # report the completed matches sitting on every other field.
    skipped = scope.filter(status=Match.Status.COMPLETED).count()
    return ctx.create_proposal(
        "propose_shift_schedule",
        f"Shift {len(assignments)} matches by {shift_mins} min"
        + (f" ({skipped} completed matches left alone)" if skipped else ""),
        {
            "assignments": assignments,
            "meta": {"shift_mins": shift_mins, "skipped_completed": skipped},
        },
    )


def propose_delete_stage(ctx: ToolContext, stage: str, stage_id: int) -> dict[str, Any]:
    if stage not in STAGE_FIELDS:
        # Falling back to a default field would count some other stage's matches and
        # offer staff a "and its 0 matches" summary to confirm, only for the applier
        # to reject the kind afterwards.
        return {
            "error": f"Unknown stage kind: {stage}. Use one of {', '.join(sorted(STAGE_FIELDS))}."
        }
    match_count = Match.objects.filter(
        tournament=ctx.tournament, **{STAGE_FIELDS[stage]: stage_id}
    ).count()
    return ctx.create_proposal(
        "propose_delete_stage",
        f"Delete {stage} #{stage_id} and its {match_count} matches",
        {"stage": stage, "stage_id": stage_id},
    )


def propose_start_tournament(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_start_tournament", "Start tournament (assign pool/Swiss teams)", {}
    )


def propose_generate_fixtures(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_generate_fixtures",
        "Populate fixtures / advance bracket stages",
        {},
    )


def propose_full_setup(
    ctx: ToolContext,
    format: str,
    pool_defs: list[dict[str, Any]] | None = None,
    swiss_defs: list[dict[str, Any]] | None = None,
    bracket_names: list[str] | None = None,
) -> dict[str, Any]:
    return ctx.create_proposal(
        "propose_full_setup",
        f"Full setup using format={format}",
        {
            "format": format,
            "pool_defs": pool_defs or [],
            "swiss_defs": swiss_defs or [],
            "bracket_names": bracket_names or [],
        },
    )


def propose_recommended_schedule(
    ctx: ToolContext,
    start_date: str,
    end_date: str | None = None,
    duration_mins: int = 75,
    slot_buffer_mins: int = 15,
    min_rest_mins: int = 60,
    day_start_hour: int = 9,
    day_end_hour: int = 18,
    lunch_start_hour: int | None = 13,
    lunch_end_hour: int | None = 14,
    field_ids: list[int] | None = None,
) -> dict[str, Any]:
    from server.tournament_agent.domain.scheduler import recommend_schedule

    result = recommend_schedule(
        tournament=ctx.tournament,
        start_date=start_date,
        end_date=end_date,
        duration_mins=duration_mins,
        slot_buffer_mins=slot_buffer_mins,
        min_rest_mins=min_rest_mins,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
        lunch_start_hour=lunch_start_hour,
        lunch_end_hour=lunch_end_hour,
        field_ids=field_ids,
    )
    assignments = result["assignments"]
    return ctx.create_proposal(
        "propose_recommended_schedule",
        f"Recommended schedule for {len(assignments)} matches ({result.get('notes', '')})",
        {"assignments": assignments, "meta": result.get("meta", {})},
    )
