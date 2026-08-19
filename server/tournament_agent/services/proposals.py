"""Apply confirmed AgentProposal payloads using tournament domain logic."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from server.core.models import Team
from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    Pool,
    PositionPool,
    SwissRound,
    Tournament,
    TournamentField,
)
from server.tournament.utils import (
    assign_swiss_round_teams,
    create_bracket_matches,
    create_pool_matches,
    create_position_pool_matches,
    create_swiss_round_matches,
    populate_fixtures,
    update_tournament_seeding,
    validate_bracket_name,
    validate_new_pool,
)
from server.tournament_agent.models import AgentProposal, ProposalStatus


class ProposalApplyError(Exception):
    pass


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        raise ProposalApplyError(f"Invalid datetime: {value}")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def apply_proposal(proposal: AgentProposal) -> dict[str, Any]:
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(f"Proposal is {proposal.status}, not pending")

    tournament = proposal.session.tournament
    tool = proposal.tool_name
    payload = proposal.payload or {}

    if tool == "propose_create_pool":
        result = _create_pool(tournament, payload)
    elif tool == "propose_create_swiss_round":
        result = _create_swiss(tournament, payload)
    elif tool == "propose_create_cross_pool":
        result = _create_cross_pool(tournament)
    elif tool == "propose_create_bracket":
        result = _create_bracket(tournament, payload)
    elif tool == "propose_create_position_pool":
        result = _create_position_pool(tournament, payload)
    elif tool == "propose_create_field":
        result = _create_field(tournament, payload)
    elif tool == "propose_create_cross_pool_matches":
        result = _create_cross_pool_matches(tournament, payload)
    elif tool == "propose_update_seeding":
        result = _update_seeding(tournament, payload)
    elif tool == "propose_update_match":
        result = _update_match(tournament, payload)
    elif tool == "propose_delete_match":
        result = _delete_match(tournament, payload)
    elif tool == "propose_bulk_schedule":
        result = _bulk_schedule(tournament, payload)
    elif tool == "propose_start_tournament":
        result = _start_tournament(tournament)
    elif tool == "propose_generate_fixtures":
        populate_fixtures(tournament.id)
        result = {"message": "Fixtures populated"}
    elif tool == "propose_full_setup":
        result = _full_setup(tournament, payload)
    else:
        raise ProposalApplyError(f"Unsupported proposal tool: {tool}")

    proposal.status = ProposalStatus.CONFIRMED
    proposal.resolved_at = timezone.now()
    proposal.save(update_fields=["status", "resolved_at"])
    return result


def reject_proposal(proposal: AgentProposal) -> None:
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(f"Proposal is {proposal.status}, not pending")
    proposal.status = ProposalStatus.REJECTED
    proposal.resolved_at = timezone.now()
    proposal.save(update_fields=["status", "resolved_at"])


def _create_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    seeding = list(payload["seeding"])
    valid, errors = validate_new_pool(tournament=tournament, new_pool=set(seeding))
    if not valid:
        raise ProposalApplyError(str(errors))
    pool_seeding: dict[int, Any] = {}
    pool_results: dict[str, Any] = {}
    for i, seed in enumerate(seeding):
        team_id = tournament.initial_seeding[str(seed)]
        pool_seeding[seed] = team_id
        pool_results[str(team_id)] = {
            "rank": i + 1,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "GF": 0,
            "GA": 0,
        }
    pool = Pool(
        sequence_number=int(payload["sequence_number"]),
        name=str(payload["name"]),
        tournament=tournament,
        initial_seeding=dict(sorted(pool_seeding.items())),
        results=pool_results,
    )
    pool.save()
    create_pool_matches(tournament, pool)
    return {"pool_id": pool.id, "name": pool.name}


def _create_swiss(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    seeding = list(payload["seeding"])
    valid, errors = validate_new_pool(tournament=tournament, new_pool=set(seeding))
    if not valid:
        raise ProposalApplyError(str(errors))
    swiss_seeding: dict[int, Any] = {}
    swiss_results: dict[str, Any] = {}
    for i, seed in enumerate(seeding):
        team_id = tournament.initial_seeding[str(seed)]
        swiss_seeding[seed] = team_id
        swiss_results[str(team_id)] = {
            "rank": i + 1,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "GF": 0,
            "GA": 0,
            "opp_strength": 0,
        }
    swiss = SwissRound(
        tournament=tournament,
        sequence_number=int(payload.get("sequence_number") or 1),
        name=str(payload["name"]),
        num_rounds=int(payload["num_rounds"]),
        initial_seeding=dict(sorted(swiss_seeding.items())),
        results=swiss_results,
    )
    swiss.save()
    create_swiss_round_matches(tournament, swiss)
    return {"swiss_round_id": swiss.id, "name": swiss.name}


def _create_cross_pool(tournament: Tournament) -> dict[str, Any]:
    cp = CrossPool.objects.create(tournament=tournament)
    return {"cross_pool_id": cp.id}


def _create_bracket(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload["name"])
    valid_name, name_error = validate_bracket_name(name)
    if not valid_name:
        raise ProposalApplyError((name_error or {}).get("message", "Invalid bracket name"))
    start, end = map(int, name.split("-"))
    bracket_seeding = {i: 0 for i in range(start, end + 1)}
    bracket = Bracket(
        sequence_number=int(payload["sequence_number"]),
        name=name,
        tournament=tournament,
        initial_seeding=dict(sorted(bracket_seeding.items())),
        current_seeding=dict(sorted(bracket_seeding.items())),
    )
    bracket.save()
    create_bracket_matches(tournament, bracket)
    return {"bracket_id": bracket.id, "name": bracket.name}


def _create_position_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    seeding = list(payload["seeding"])
    pool_seeding = {seed: 0 for seed in seeding}
    results = {str(seed): {"rank": i + 1, "wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0} for i, seed in enumerate(seeding)}
    pp = PositionPool(
        sequence_number=int(payload["sequence_number"]),
        name=str(payload["name"]),
        tournament=tournament,
        initial_seeding=dict(sorted(pool_seeding.items())),
        results=results,
    )
    pp.save()
    create_position_pool_matches(tournament, pp)
    return {"position_pool_id": pp.id, "name": pp.name}


def _create_field(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ProposalApplyError("Field name is required")
    if TournamentField.objects.filter(tournament=tournament, name__iexact=name).exists():
        raise ProposalApplyError(f"A field named '{name}' already exists in this tournament")

    field = TournamentField(
        tournament=tournament,
        name=name,
        address=payload.get("address") or None,
        is_broadcasted=bool(payload.get("is_broadcasted") or False),
    )
    try:
        field.full_clean()
    except DjangoValidationError as exc:
        raise ProposalApplyError(str(exc)) from exc
    field.save()
    return {"field_id": field.id, "name": field.name}


def _create_cross_pool_matches(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    cross_pool = CrossPool.objects.filter(tournament=tournament).first()
    if cross_pool is None:
        raise ProposalApplyError(
            "No cross pool stage exists yet. Confirm a create-cross-pool proposal first."
        )

    sequence_number = int(payload.get("sequence_number") or 1)
    raw_pairs = payload.get("seed_pairs") or []
    if not raw_pairs:
        raise ProposalApplyError("No seed pairs given")

    num_teams = tournament.teams.count()
    existing_pairs = {
        frozenset((m.placeholder_seed_1, m.placeholder_seed_2))
        for m in Match.objects.filter(cross_pool=cross_pool, sequence_number=sequence_number)
    }
    seen: set[frozenset[int]] = set()
    pairs: list[tuple[int, int]] = []
    for raw in raw_pairs:
        seed_1, seed_2 = int(raw[0]), int(raw[1])
        if seed_1 == seed_2:
            raise ProposalApplyError(f"A team cannot play itself (seed {seed_1})")
        for seed in (seed_1, seed_2):
            if num_teams and not 1 <= seed <= num_teams:
                raise ProposalApplyError(f"Seed {seed} is out of range (1-{num_teams})")
        key = frozenset((seed_1, seed_2))
        if key in existing_pairs or key in seen:
            raise ProposalApplyError(
                f"Cross pool match {seed_1} v {seed_2} already exists in round {sequence_number}"
            )
        seen.add(key)
        pairs.append((min(seed_1, seed_2), max(seed_1, seed_2)))

    match_ids = []
    for seed_1, seed_2 in pairs:
        match = Match.objects.create(
            tournament=tournament,
            cross_pool=cross_pool,
            name="Cross Pool",
            sequence_number=sequence_number,
            placeholder_seed_1=seed_1,
            placeholder_seed_2=seed_2,
        )
        match_ids.append(match.id)
    return {"match_ids": match_ids, "count": len(match_ids)}


def _update_seeding(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    seeding = payload.get("seeding") or {}
    normalized = {int(k): int(v) for k, v in seeding.items()}
    ok, error = update_tournament_seeding(tournament, normalized)
    if not ok:
        raise ProposalApplyError((error or {}).get("message", "Cannot update seeding"))
    return {"seeding": {str(k): v for k, v in normalized.items()}}


def _update_match(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    if "time" in payload and payload["time"] is not None:
        match.time = _parse_time(payload["time"])
    if payload.get("field_id") is not None:
        match.field = TournamentField.objects.get(id=payload["field_id"], tournament=tournament)
    if payload.get("duration_mins") is not None:
        match.duration_mins = int(payload["duration_mins"])
    if match.time and match.field:
        match.status = Match.Status.SCHEDULED
    match.save()
    return {"match_id": match.id}


def _delete_match(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    mid = match.id
    match.delete()
    return {"deleted_match_id": mid}


def _bulk_schedule(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    updated = []
    for row in payload.get("assignments") or []:
        match = Match.objects.get(id=row["match_id"], tournament=tournament)
        match.time = _parse_time(row["time"])
        match.field = TournamentField.objects.get(id=row["field_id"], tournament=tournament)
        if row.get("duration_mins") is not None:
            match.duration_mins = int(row["duration_mins"])
        match.status = Match.Status.SCHEDULED
        match.save()
        updated.append(match.id)
    return {"updated_match_ids": updated}


def _start_tournament(tournament: Tournament) -> dict[str, Any]:
    pool_matches = Match.objects.filter(tournament=tournament).exclude(pool__isnull=True)
    for match in pool_matches:
        team_1_id = tournament.initial_seeding[str(match.placeholder_seed_1)]
        team_2_id = tournament.initial_seeding[str(match.placeholder_seed_2)]
        match.team_1 = Team.objects.get(id=team_1_id)
        match.team_2 = Team.objects.get(id=team_2_id)
        match.status = Match.Status.SCHEDULED
        match.save()
    for swiss_round in SwissRound.objects.filter(tournament=tournament):
        assign_swiss_round_teams(tournament, swiss_round, 1)
    tournament.status = Tournament.Status.LIVE
    tournament.save(update_fields=["status"])
    return {"status": tournament.status}


def _full_setup(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    created: dict[str, Any] = {"pools": [], "swiss": [], "brackets": []}
    for i, pool_def in enumerate(payload.get("pool_defs") or []):
        created["pools"].append(
            _create_pool(
                tournament,
                {
                    "name": pool_def.get("name") or chr(ord("A") + i),
                    "sequence_number": pool_def.get("sequence_number") or (i + 1),
                    "seeding": pool_def["seeding"],
                },
            )
        )
    for i, swiss_def in enumerate(payload.get("swiss_defs") or []):
        created["swiss"].append(
            _create_swiss(
                tournament,
                {
                    "name": swiss_def.get("name") or chr(ord("A") + i),
                    "sequence_number": swiss_def.get("sequence_number") or (i + 1),
                    "seeding": swiss_def["seeding"],
                    "num_rounds": swiss_def.get("num_rounds") or 3,
                },
            )
        )
    for i, name in enumerate(payload.get("bracket_names") or []):
        created["brackets"].append(
            _create_bracket(tournament, {"name": name, "sequence_number": i + 1})
        )
    return created
