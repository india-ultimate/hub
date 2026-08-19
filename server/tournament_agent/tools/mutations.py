"""Proposal tools: everything the agent can ask staff to approve.

Nothing here writes to the tournament. Each returns a pending `AgentProposal`;
`services.proposals` is what applies one once staff hit Confirm. Validation that
can be done at propose time belongs here, so staff are never shown a plan that
will only fail on Confirm.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from server.tournament.models import Match, TournamentField
from server.tournament_agent.domain.format import (
    bracket_match_plan,
    bracket_proposal_summary,
    canonical_stage_name,
    labeled_pool_defs,
    labeled_snake_pools,
    rewrite_sequential_pool_defs,
    sequential_pool_seed_error,
)
from server.tournament_agent.domain.validate import DEFAULT_MATCH_MINS
from server.tournament_agent.tools.context import ToolContext
from server.tournament_agent.tools.queries import STAGE_FIELDS, STAGE_MODELS, match_queryset

MIN_POOLS = 2
MIN_TEAMS_PER_POOL = 2


def propose_pool_stage(ctx: ToolContext, pool_count: int) -> dict[str, Any]:
    """Propose the whole pool stage. Seeds are derived here, never by the model.

    `propose_create_pool` still exists for adding one pool to an event that already
    has some, but the setup path does not offer it: a seed list the model wrote is a
    seed list that can be wrong, and the snake for N teams in M pools is arithmetic.
    """
    team_count = len(ctx.tournament.initial_seeding or {}) or ctx.tournament.teams.count()
    if team_count < MIN_POOLS * MIN_TEAMS_PER_POOL:
        message = f"{team_count} teams is too few to split into pools."
        return {"error": message, "message": message}
    try:
        count = int(pool_count)
    except (TypeError, ValueError):
        count = 0
    max_pools = team_count // MIN_TEAMS_PER_POOL
    if not MIN_POOLS <= count <= max_pools:
        message = (
            f"pool_count must be between {MIN_POOLS} and {max_pools} for "
            f"{team_count} teams. Ask staff which they want."
        )
        return {"error": message, "message": message}

    snake = labeled_snake_pools(team_count, count)
    pools = [
        {"name": label, "sequence_number": i, "seeding": seeds}
        for i, (label, seeds) in enumerate(snake.items(), start=1)
    ]
    rendered = ", ".join(f"{row['name']}={row['seeding']}" for row in pools)
    return ctx.create_proposal(
        "propose_pool_stage",
        f"Create {count} pools by snake draft: {rendered}",
        {"pools": pools},
    )


def propose_create_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    team_count = len(ctx.tournament.initial_seeding or {}) or ctx.tournament.teams.count()
    blocked = sequential_pool_seed_error(team_count, list(seeding))
    if blocked:
        return blocked
    label = canonical_stage_name(name, "A")
    return ctx.create_proposal(
        "propose_create_pool",
        f"Create pool {label} with seeds {seeding}",
        {"name": label, "sequence_number": sequence_number, "seeding": seeding},
    )


def propose_create_swiss_round(
    ctx: ToolContext, name: str, seeding: list[int], num_rounds: int, sequence_number: int = 1
) -> dict[str, Any]:
    label = canonical_stage_name(name, "A")
    return ctx.create_proposal(
        "propose_create_swiss_round",
        f"Create Swiss group {label} ({num_rounds} rounds) with seeds {seeding}",
        {
            "name": label,
            "seeding": seeding,
            "num_rounds": num_rounds,
            "sequence_number": sequence_number,
        },
    )


def propose_create_cross_pool(ctx: ToolContext) -> dict[str, Any]:
    return ctx.create_proposal("propose_create_cross_pool", "Create cross pool stage", {})


def propose_create_bracket(ctx: ToolContext, name: str, sequence_number: int) -> dict[str, Any]:
    try:
        matches = bracket_match_plan(name)
    except ValueError as exc:
        return {"error": str(exc), "message": str(exc)}
    return ctx.create_proposal(
        "propose_create_bracket",
        bracket_proposal_summary(name, matches),
        {"name": name, "sequence_number": sequence_number, "matches": matches},
    )


def propose_create_position_pool(
    ctx: ToolContext, name: str, sequence_number: int, seeding: list[int]
) -> dict[str, Any]:
    label = canonical_stage_name(name, "E")
    return ctx.create_proposal(
        "propose_create_position_pool",
        f"Create position pool {label} with seeds {seeding}",
        {"name": label, "sequence_number": sequence_number, "seeding": seeding},
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


def _tournament_field(ctx: ToolContext, field_id: int) -> TournamentField | None:
    return TournamentField.objects.filter(id=field_id, tournament=ctx.tournament).first()


def propose_update_field(
    ctx: ToolContext,
    field_id: int,
    name: str | None = None,
    address: str | None = None,
    is_broadcasted: bool | None = None,
) -> dict[str, Any]:
    field = _tournament_field(ctx, field_id)
    if field is None:
        return {"error": f"No field #{field_id} on this tournament."}
    if name is None and address is None and is_broadcasted is None:
        return {"error": "Provide at least one of name, address, or is_broadcasted."}

    new_name = name.strip() if name is not None else None
    if name is not None and not new_name:
        return {"error": "Field name cannot be empty."}
    if new_name and (
        TournamentField.objects.filter(tournament=ctx.tournament, name__iexact=new_name)
        .exclude(id=field.id)
        .exists()
    ):
        return {"error": f"A field named '{new_name}' already exists in this tournament"}

    bits: list[str] = []
    payload: dict[str, Any] = {"field_id": field.id, "current_name": field.name}
    if new_name is not None:
        payload["name"] = new_name
        if new_name != field.name:
            bits.append(f"rename '{field.name}' to '{new_name}'")
    if address is not None:
        payload["address"] = address.strip() or None
        bits.append(
            f"set address to '{payload['address']}'" if payload["address"] else "clear address"
        )
    if is_broadcasted is not None:
        payload["is_broadcasted"] = is_broadcasted
        bits.append("mark as broadcast" if is_broadcasted else "unmark broadcast")
    if not bits:
        return {"error": "No changes from the current field."}

    return ctx.create_proposal("propose_update_field", "Update field: " + "; ".join(bits), payload)


def propose_delete_field(ctx: ToolContext, field_id: int) -> dict[str, Any]:
    field = _tournament_field(ctx, field_id)
    if field is None:
        return {"error": f"No field #{field_id} on this tournament."}
    match_count = Match.objects.filter(field=field).count()
    if match_count:
        return {
            "error": (
                f"Field '{field.name}' still has {match_count} match(es) assigned. "
                "Move those matches to another field first, then delete."
            )
        }
    return ctx.create_proposal(
        "propose_delete_field",
        f"Delete field '{field.name}'",
        {"field_id": field.id, "name": field.name},
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
    seed_1: int | None = None,
    seed_2: int | None = None,
) -> dict[str, Any]:
    if seed_1 is None and seed_2 is None:
        summary = f"Update match {match_id}"
    elif seed_1 is None or seed_2 is None:
        return {"error": "Pass both seed_1 and seed_2 to change a pairing"}
    elif seed_1 == seed_2:
        return {"error": f"A team cannot play itself (seed {seed_1})"}
    else:
        summary = f"Update match {match_id} to {seed_1}v{seed_2}"
    return ctx.create_proposal(
        "propose_update_match",
        summary,
        {
            "match_id": match_id,
            "time": time,
            "field_id": field_id,
            "duration_mins": duration_mins,
            "seed_1": seed_1,
            "seed_2": seed_2,
        },
    )


def propose_update_match_seeds(ctx: ToolContext, updates: list[dict[str, Any]]) -> dict[str, Any]:
    """Rewrite placeholder seeds on existing matches (one Confirm for the set)."""
    if not updates:
        return {"error": "No seed updates given"}
    rows: list[dict[str, int]] = []
    labels: list[str] = []
    seen_ids: set[int] = set()
    for raw in updates:
        try:
            match_id = int(raw["match_id"])
            seed_1 = int(raw["seed_1"])
            seed_2 = int(raw["seed_2"])
        except (KeyError, TypeError, ValueError):
            return {"error": "Each update needs match_id, seed_1 and seed_2"}
        if seed_1 == seed_2:
            return {"error": f"A team cannot play itself (seed {seed_1})"}
        if match_id in seen_ids:
            return {"error": f"Match {match_id} is listed twice"}
        seen_ids.add(match_id)
        rows.append({"match_id": match_id, "seed_1": seed_1, "seed_2": seed_2})
        labels.append(f"{seed_1}v{seed_2}")
    return ctx.create_proposal(
        "propose_update_match_seeds",
        f"Update match seeds: {', '.join(labels)}",
        {"updates": rows},
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
        # to reject the kind afterwards. "swiss_round" is the Match FK, not a kind.
        return {
            "error": f"Unknown stage kind: {stage}. Use one of {', '.join(sorted(STAGE_FIELDS))}."
        }
    row = STAGE_MODELS[stage].objects.filter(id=stage_id, tournament=ctx.tournament).first()
    if row is None:
        return {"error": f"No {stage} #{stage_id} on this tournament."}
    match_count = Match.objects.filter(
        tournament=ctx.tournament, **{STAGE_FIELDS[stage]: stage_id}
    ).count()
    name = getattr(row, "name", None) or ("Cross Pool" if stage == "cross_pool" else None)
    label = f"{stage} {name}" if name else f"{stage} #{stage_id}"
    return ctx.create_proposal(
        "propose_delete_stage",
        f"Delete {label} and its {match_count} matches",
        {"stage": stage, "stage_id": stage_id, "name": name},
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
    team_count = len(ctx.tournament.initial_seeding or {}) or ctx.tournament.teams.count()
    pools = labeled_pool_defs(rewrite_sequential_pool_defs(list(pool_defs or []), team_count))
    return ctx.create_proposal(
        "propose_full_setup",
        f"Full setup using format={format}",
        {
            "format": format,
            "pool_defs": pools,
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
    day_start_hour: int = 7,
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
    unplaced = int((result.get("meta") or {}).get("unplaced") or 0)
    if not assignments:
        return {
            "error": result.get("notes") or "Could not place any matches",
            "message": (
                "No proposal created. Add fields first, or relax duration / day "
                "window, or build an exact grid with propose_bulk_schedule."
            ),
        }
    if unplaced:
        return {
            "error": result.get("notes") or f"{unplaced} matches could not be placed",
            "placed": len(assignments),
            "unplaced": unplaced,
            "message": (
                "No proposal created — a partial grid is not confirmable. Relax "
                "constraints, add a field, or use propose_bulk_schedule."
            ),
        }
    return ctx.create_proposal(
        "propose_recommended_schedule",
        f"Recommended schedule for {len(assignments)} matches ({result.get('notes', '')})",
        {"assignments": assignments, "meta": result.get("meta", {})},
    )
