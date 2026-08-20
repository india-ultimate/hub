"""Apply confirmed AgentProposal payloads using tournament domain logic.

Stage creation and tournament start live in `server.tournament.utils` so that this
path and the staff API share one implementation and cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    Registration,
    Tournament,
    TournamentField,
)
from server.tournament.schema import SpiritScoreUpdateSchema
from server.tournament.utils import (
    build_bracket,
    build_pool,
    build_position_pool,
    build_swiss_round,
    create_spirit_scores,
    get_bracket_match_name,
    parse_match_time,
    populate_fixtures,
    update_match_score_and_results,
    update_tournament_seeding,
    update_tournament_spirit_rankings,
)
from server.tournament.utils import start_tournament as begin_tournament
from server.tournament_agent.domain.format import canonical_stage_name
from server.tournament_agent.models import (
    AgentProposal,
    MessageKind,
    MessageRole,
    ProposalStatus,
    TournamentAgentMessage,
)
from server.tournament_agent.tools import STAGE_FIELDS, STAGE_MODELS


class ProposalApplyError(Exception):
    pass


class _AlreadyResolved(Exception):  # noqa: N818 — a race, not an apply failure
    """Another Confirm got to this row first. Distinct so it never sets last_error."""


# Confirm and Reject happen outside the turn loop, so without this the agent never
# learns what became of a plan it made: `pending` rows drop off the state block on
# Confirm and nothing takes their place. Recorded as a message so the outcome keeps
# its position in the conversation, and surfaced again in the snapshot's
# "Applied this session" list.
def _record_outcome(proposal: AgentProposal, text: str, outcome: str) -> None:
    TournamentAgentMessage.objects.create(
        session=proposal.session,
        role=MessageRole.SYSTEM,
        content=text,
        message_kind=MessageKind.PROPOSAL_REF,
        payload={"proposal_id": proposal.id, "outcome": outcome},
    )


def _parse_time(value: str | None) -> datetime | None:
    """Times go through the same helper the classic manager uses.

    A match scheduled by the agent and the same match rescheduled by hand have to
    end up on the same instant, so there is one interpretation of a time string
    and both callers share it.
    """
    if not value:
        return None
    try:
        return parse_match_time(value)
    except ValueError as exc:
        raise ProposalApplyError(str(exc)) from exc


def _readable(exc: Exception) -> str:
    """Turn a domain/database failure into something staff can act on."""
    if isinstance(exc, ObjectDoesNotExist):
        model = type(exc).__qualname__.removesuffix(".DoesNotExist")
        return f"{model} no longer exists — the tournament changed since this was proposed"
    if isinstance(exc, IntegrityError):
        text = str(exc)
        if "time" in text and "field" in text:
            return (
                "Two matches would occupy the same field at the same time. "
                "Reject this and ask the agent for a grid without double-booked slots."
            )
        return f"The database rejected the change: {exc}"
    if isinstance(exc, KeyError):
        return f"The proposal is missing {exc}"
    return str(exc)


def _record_apply_error(proposal: AgentProposal, message: str) -> None:
    proposal.last_error = (message or "")[:2000]
    proposal.save(update_fields=["last_error"])


def _not_pending_message(status: str) -> str:
    if status == ProposalStatus.EXPIRED:
        # Two ways to get here — a newer plan from the same tool replaced this one,
        # or the conversation was cleared. Say what to do rather than just the status.
        return (
            "This plan is no longer current — it was replaced by a newer one, or the "
            "conversation was cleared. Ask the agent again to get a fresh proposal."
        )
    if status == ProposalStatus.CONFIRMED:
        return "This proposal has already been applied."
    return f"Proposal is {status}, not pending"


def apply_proposal(proposal: AgentProposal) -> dict[str, Any]:
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(_not_pending_message(proposal.status))

    apply_fn = _APPLIERS.get(proposal.tool_name)
    if apply_fn is None:
        raise ProposalApplyError(f"Unsupported proposal tool: {proposal.tool_name}")

    try:
        # Every applier below writes more than one row; without this a failure
        # part-way leaves the tournament half-changed and the proposal pending.
        with transaction.atomic():
            # Two Confirms on the same card — a double click, or two directors on
            # one tournament — would otherwise both read PENDING and both apply.
            # No-op on SQLite, a real row lock on Postgres.
            locked = (
                AgentProposal.objects.select_for_update()
                .select_related("session__tournament")
                .get(id=proposal.id)
            )
            if locked.status != ProposalStatus.PENDING:
                raise _AlreadyResolved(_not_pending_message(locked.status))
            result = apply_fn(locked.session.tournament, locked.payload or {})
            locked.status = ProposalStatus.CONFIRMED
            locked.resolved_at = timezone.now()
            locked.last_error = ""
            locked.save(update_fields=["status", "resolved_at", "last_error"])
    except _AlreadyResolved as exc:
        # Not an apply failure: nothing was attempted, so last_error stays as it was.
        proposal.refresh_from_db()
        raise ProposalApplyError(str(exc)) from exc
    except ProposalApplyError as exc:
        _record_apply_error(proposal, str(exc))
        _record_outcome(
            proposal,
            f"Proposal #{proposal.id} ({proposal.tool_name}) was confirmed by staff but "
            f"failed to apply: {exc}. Re-propose with a corrected payload — do not "
            "reuse the failed one.",
            "failed",
        )
        raise
    except (
        ObjectDoesNotExist,
        IntegrityError,
        DjangoValidationError,
        ValueError,
        KeyError,
    ) as exc:
        message = _readable(exc)
        _record_apply_error(proposal, message)
        _record_outcome(
            proposal,
            f"Proposal #{proposal.id} ({proposal.tool_name}) was confirmed by staff but "
            f"failed to apply: {message}. Re-propose with a corrected payload — do not "
            "reuse the failed one.",
            "failed",
        )
        raise ProposalApplyError(message) from exc

    proposal.refresh_from_db()
    _record_outcome(
        proposal,
        f"Proposal #{proposal.id} ({proposal.tool_name}) was confirmed by staff and "
        f"applied: {proposal.summary}",
        "confirmed",
    )
    return result


def reject_proposal(proposal: AgentProposal) -> None:
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(_not_pending_message(proposal.status))
    proposal.status = ProposalStatus.REJECTED
    proposal.resolved_at = timezone.now()
    proposal.save(update_fields=["status", "resolved_at"])
    _record_outcome(
        proposal,
        f"Proposal #{proposal.id} ({proposal.tool_name}) was rejected by staff and will "
        f"not be applied: {proposal.summary}",
        "rejected",
    )


def _create_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    pool = build_pool(
        tournament,
        name=canonical_stage_name(str(payload.get("name") or ""), "A"),
        sequence_number=int(payload["sequence_number"]),
        seeding=list(payload["seeding"]),
    )
    return {"pool_id": pool.id, "name": pool.name}


def _create_pool_stage(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    """Build every pool of the stage in one go, in the order they were proposed."""
    created = []
    for row in payload.get("pools") or []:
        pool = build_pool(
            tournament,
            name=canonical_stage_name(str(row.get("name") or ""), "A"),
            sequence_number=int(row["sequence_number"]),
            seeding=list(row["seeding"]),
        )
        created.append({"pool_id": pool.id, "name": pool.name})
    if not created:
        raise ProposalApplyError("The proposal listed no pools")
    return {"pools": created}


def _create_swiss(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    swiss_round = build_swiss_round(
        tournament,
        name=canonical_stage_name(str(payload.get("name") or ""), "A"),
        sequence_number=int(payload.get("sequence_number") or 1),
        seeding=list(payload["seeding"]),
        num_rounds=int(payload["num_rounds"]),
    )
    return {"swiss_round_id": swiss_round.id, "name": swiss_round.name}


def _create_bracket(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    bracket = build_bracket(
        tournament,
        name=str(payload["name"]),
        sequence_number=int(payload["sequence_number"]),
    )
    return {"bracket_id": bracket.id, "name": bracket.name}


def _create_position_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    position_pool = build_position_pool(
        tournament,
        name=canonical_stage_name(str(payload.get("name") or ""), "E"),
        sequence_number=int(payload["sequence_number"]),
        seeding=list(payload["seeding"]),
    )
    return {"position_pool_id": position_pool.id, "name": position_pool.name}


def _create_cross_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    cross_pool = CrossPool.objects.create(tournament=tournament)
    return {"cross_pool_id": cross_pool.id}


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
    field.full_clean()
    field.save()
    return {"field_id": field.id, "name": field.name}


def _get_field(tournament: Tournament, field_id: int) -> TournamentField:
    field = TournamentField.objects.filter(id=field_id, tournament=tournament).first()
    if field is None:
        raise ProposalApplyError(f"No field #{field_id} on this tournament")
    return field


def _update_field(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    field = _get_field(tournament, int(payload["field_id"]))
    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ProposalApplyError("Field name cannot be empty")
        if (
            TournamentField.objects.filter(tournament=tournament, name__iexact=name)
            .exclude(id=field.id)
            .exists()
        ):
            raise ProposalApplyError(f"A field named '{name}' already exists in this tournament")
        field.name = name
    if "address" in payload:
        address = payload.get("address")
        if address:
            field.address = str(address).strip() or None
        else:
            field.address = None
    if "is_broadcasted" in payload and payload["is_broadcasted"] is not None:
        field.is_broadcasted = bool(payload["is_broadcasted"])
    field.full_clean()
    field.save()
    return {"field_id": field.id, "name": field.name}


def _delete_field(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    field = _get_field(tournament, int(payload["field_id"]))
    match_count = Match.objects.filter(field=field).count()
    if match_count:
        raise ProposalApplyError(
            f"Field '{field.name}' still has {match_count} match(es) assigned. "
            "Move those matches to another field first, then delete."
        )
    field_id, name = field.id, field.name
    field.delete()
    return {"field_id": field_id, "name": name}


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

    match_ids = [
        Match.objects.create(
            tournament=tournament,
            cross_pool=cross_pool,
            name="Cross Pool",
            sequence_number=sequence_number,
            placeholder_seed_1=seed_1,
            placeholder_seed_2=seed_2,
        ).id
        for seed_1, seed_2 in pairs
    ]
    return {"match_ids": match_ids, "count": len(match_ids)}


def _update_seeding(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    seeding = {int(k): int(v) for k, v in (payload.get("seeding") or {}).items()}
    ok, error = update_tournament_seeding(tournament, seeding)
    if not ok:
        raise ProposalApplyError((error or {}).get("message", "Cannot update seeding"))
    return {"seeding": {str(k): v for k, v in seeding.items()}}


def _set_slot(
    tournament: Tournament,
    match: Match,
    *,
    time: str | None,
    field_id: int | None,
    duration_mins: int | None,
) -> None:
    """Place a match in a time/field slot.

    Deliberately never touches `status`: that tracks team assignment, not slot
    assignment. Marking a match Scheduled here would hide it from
    populate_fixtures, which only fills teams into Yet-To-Fix matches.
    """
    if match.status == Match.Status.COMPLETED:
        raise ProposalApplyError(f"Match {match.id} is already completed and cannot be rescheduled")
    if time is not None:
        match.time = _parse_time(time)
    if field_id is not None:
        match.field = TournamentField.objects.get(id=field_id, tournament=tournament)
    if duration_mins is not None:
        match.duration_mins = int(duration_mins)
    match.save()


def _seed_keys(seeding: Any) -> list[int]:
    if not isinstance(seeding, dict):
        return []
    return [int(key) for key in seeding if str(key).isdigit()]


def _match_name_for_seeds(match: Match, seed_1: int, seed_2: int) -> str | None:
    lo, hi = min(seed_1, seed_2), max(seed_1, seed_2)
    if match.pool_id and match.pool is not None:
        return f"{match.pool.name}{lo} v {match.pool.name}{hi}"
    if match.position_pool_id and match.position_pool is not None:
        return f"{match.position_pool.name}{lo} v {match.position_pool.name}{hi}"
    if match.bracket_id and match.bracket is not None:
        keys = sorted(_seed_keys(match.bracket.initial_seeding))
        if keys:
            return get_bracket_match_name(keys[0], keys[-1], seed_1, seed_2) or match.name
    return match.name


def _seed_ceiling(tournament: Tournament, match: Match) -> int:
    ceiling = tournament.teams.count() or 0
    seeding = tournament.current_seeding or tournament.initial_seeding or {}
    keys = _seed_keys(seeding)
    if keys:
        ceiling = max(ceiling, *keys)
    qs = Match.objects.filter(tournament=tournament)
    if match.bracket_id:
        qs = qs.filter(bracket_id=match.bracket_id)
        if match.bracket is not None:
            keys = _seed_keys(match.bracket.initial_seeding)
            if keys:
                ceiling = max(ceiling, *keys)
    elif match.pool_id:
        qs = qs.filter(pool_id=match.pool_id)
    elif match.cross_pool_id:
        qs = qs.filter(cross_pool_id=match.cross_pool_id)
    elif match.position_pool_id:
        qs = qs.filter(position_pool_id=match.position_pool_id)
    elif match.swiss_round_id:
        qs = qs.filter(swiss_round_id=match.swiss_round_id)
    for row in qs.only("placeholder_seed_1", "placeholder_seed_2"):
        ceiling = max(ceiling, row.placeholder_seed_1, row.placeholder_seed_2)
    return max(ceiling, 1)


def _round_queryset(tournament: Tournament, match: Match) -> QuerySet[Match]:
    qs = Match.objects.filter(tournament=tournament, sequence_number=match.sequence_number)
    if match.bracket_id:
        return qs.filter(bracket_id=match.bracket_id)
    if match.pool_id:
        return qs.filter(pool_id=match.pool_id)
    if match.cross_pool_id:
        return qs.filter(cross_pool_id=match.cross_pool_id)
    if match.position_pool_id:
        return qs.filter(position_pool_id=match.position_pool_id)
    if match.swiss_round_id:
        return qs.filter(swiss_round_id=match.swiss_round_id)
    return qs.none()


def _assert_round_seeds_unique(
    tournament: Tournament, match: Match, pending: dict[int, tuple[int, int]]
) -> None:
    seeds: list[int] = []
    for row in _round_queryset(tournament, match):
        seed_1, seed_2 = pending.get(row.id, (row.placeholder_seed_1, row.placeholder_seed_2))
        seeds.extend((seed_1, seed_2))
    seen: set[int] = set()
    for seed in seeds:
        if seed in seen:
            raise ProposalApplyError(
                f"Seed {seed} would appear twice in the same round. "
                "Rewrite every pairing that shares that seed in one proposal."
            )
        seen.add(seed)


def _assign_teams_from_seeds(
    match: Match, tournament: Tournament, seed_1: int, seed_2: int
) -> None:
    if not (match.team_1_id or match.team_2_id):
        return
    seeding = tournament.current_seeding or tournament.initial_seeding or {}
    team_1 = seeding.get(str(seed_1))
    team_2 = seeding.get(str(seed_2))
    if team_1:
        match.team_1_id = int(team_1)
    if team_2:
        match.team_2_id = int(team_2)


def _write_match_seeds(match: Match, tournament: Tournament, seed_1: int, seed_2: int) -> None:
    if match.status == Match.Status.COMPLETED:
        raise ProposalApplyError(f"Match {match.id} is completed — its seeds cannot be changed")
    if seed_1 == seed_2:
        raise ProposalApplyError(f"A team cannot play itself (seed {seed_1})")
    ceiling = _seed_ceiling(tournament, match)
    for seed in (seed_1, seed_2):
        if seed < 1 or seed > ceiling:
            raise ProposalApplyError(f"Seed {seed} is out of range (1-{ceiling})")
    match.placeholder_seed_1 = seed_1
    match.placeholder_seed_2 = seed_2
    name = _match_name_for_seeds(match, seed_1, seed_2)
    if name:
        match.name = name
    _assign_teams_from_seeds(match, tournament, seed_1, seed_2)
    match.save()


def _load_match(tournament: Tournament, match_id: int) -> Match:
    try:
        return Match.objects.select_related("pool", "bracket", "position_pool").get(
            id=match_id, tournament=tournament
        )
    except Match.DoesNotExist as exc:
        raise ProposalApplyError(f"Match {match_id} no longer exists") from exc


def _update_match(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = _load_match(tournament, int(payload["match_id"]))
    seed_1 = payload.get("seed_1")
    seed_2 = payload.get("seed_2")
    if seed_1 is not None or seed_2 is not None:
        if seed_1 is None or seed_2 is None:
            raise ProposalApplyError("Pass both seed_1 and seed_2 to change a pairing")
        pending = {match.id: (int(seed_1), int(seed_2))}
        _assert_round_seeds_unique(tournament, match, pending)
        _write_match_seeds(match, tournament, int(seed_1), int(seed_2))
        match.refresh_from_db()
    _set_slot(
        tournament,
        match,
        time=payload.get("time"),
        field_id=payload.get("field_id"),
        duration_mins=payload.get("duration_mins"),
    )
    return {
        "match_id": match.id,
        "placeholder_seed_1": match.placeholder_seed_1,
        "placeholder_seed_2": match.placeholder_seed_2,
    }


def _update_match_seeds(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    updates = list(payload.get("updates") or [])
    if not updates:
        raise ProposalApplyError("No seed updates given")
    pending: dict[int, tuple[int, int]] = {}
    matches: list[Match] = []
    for row in updates:
        match = _load_match(tournament, int(row["match_id"]))
        seed_1, seed_2 = int(row["seed_1"]), int(row["seed_2"])
        pending[match.id] = (seed_1, seed_2)
        matches.append(match)
    for match in matches:
        _assert_round_seeds_unique(tournament, match, pending)
    for match in matches:
        seed_1, seed_2 = pending[match.id]
        _write_match_seeds(match, tournament, seed_1, seed_2)
    return {
        "match_ids": [m.id for m in matches],
        "count": len(matches),
    }


def _delete_match(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    if match.status == Match.Status.COMPLETED:
        raise ProposalApplyError(
            f"Match {match.id} is completed — deleting it would leave its result "
            "in the standings with no match behind it"
        )
    match_id = match.id
    match.delete()
    return {"deleted_match_id": match_id}


def _bulk_schedule(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    assignments = list(payload.get("assignments") or [])
    seen_slots: dict[tuple[str, int], Any] = {}
    for row in assignments:
        time = row.get("time")
        field_id = row.get("field_id")
        if time is None or field_id is None:
            continue
        key = (str(time), int(field_id))
        prior = seen_slots.get(key)
        if prior is not None:
            raise ProposalApplyError(
                f"Matches {prior} and {row.get('match_id')} are both on field "
                f"{field_id} at {time}. One field cannot host two matches at the "
                "same start. Reject this and ask the agent for a corrected grid."
            )
        seen_slots[key] = row.get("match_id")

    updated = []
    for row in assignments:
        # `_set_slot` skips whatever is None, which is right for a partial
        # `propose_update_match` but wrong here: a row missing its slot would leave
        # the match untouched and still be reported back as scheduled.
        missing = [key for key in ("time", "field_id") if row.get(key) is None]
        if missing:
            raise ProposalApplyError(
                f"The assignment for match {row.get('match_id')} is missing {', '.join(missing)}"
            )
        match = Match.objects.get(id=row["match_id"], tournament=tournament)
        _set_slot(
            tournament,
            match,
            time=row.get("time"),
            field_id=row.get("field_id"),
            duration_mins=row.get("duration_mins"),
        )
        updated.append(match.id)
    return {"updated_match_ids": updated}


def _match_score(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    if match.status == Match.Status.COMPLETED:
        raise ProposalApplyError(
            f"Match {match.id} already has a result. Scores accumulate into the standings, "
            "so re-entering one would double-count it — correct it in Django admin instead."
        )
    if match.status != Match.Status.SCHEDULED or match.team_1_id is None or match.team_2_id is None:
        raise ProposalApplyError(
            f"Match {match.id} has no teams assigned yet, so it cannot be scored"
        )

    scores = []
    for key in ("score_team_1", "score_team_2"):
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ProposalApplyError(f"{key} must be a score of 0 or more")
        scores.append(value)

    if payload.get("forfeit") and 0 not in scores:
        # There is no walkover status: a forfeit is a normal result that happens to
        # be 15-0 to the team that showed up. Without this the flag would only ever
        # be decoration on the summary, and the applied match would be
        # indistinguishable from a game both teams played.
        raise ProposalApplyError(
            "A forfeit is recorded as a score in favour of the team that showed up, "
            f"so one side must be 0 — got {scores[0]}-{scores[1]}"
        )

    # Applies the result, recomputes pool/Swiss standings and current seeding,
    # swaps bracket/cross-pool seeds on an upset, and fills the next stage.
    update_match_score_and_results(match, scores[0], scores[1])
    populate_fixtures(tournament.id)
    return {"match_id": match.id, "score": scores, "status": match.status}


SPIRIT_COMPONENTS = ("rules", "fouls", "fair", "positive", "communication")
MAX_SPIRIT_COMPONENT = 4
MAX_SPIRIT_COMMENT_CHARS = 500

# block name -> (Match attribute, which team the block is about)
SPIRIT_TARGETS = {
    "team_1_received": ("spirit_score_team_1", 1),
    "team_2_received": ("spirit_score_team_2", 2),
    "team_1_self": ("self_spirit_score_team_1", 1),
    "team_2_self": ("self_spirit_score_team_2", 2),
}


def _spirit_block(match: Match, name: str, block: dict[str, Any]) -> SpiritScoreUpdateSchema:
    for component in SPIRIT_COMPONENTS:
        value = block.get(component)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProposalApplyError(f"{name}.{component} is required and must be a number")
        if not 0 <= value <= MAX_SPIRIT_COMPONENT:
            # PositiveIntegerField would happily store 99 and silently skew the ranking.
            raise ProposalApplyError(
                f"{name}.{component} must be between 0 and {MAX_SPIRIT_COMPONENT}"
            )

    comments = block.get("comments")
    if comments is not None and len(str(comments)) > MAX_SPIRIT_COMMENT_CHARS:
        raise ProposalApplyError(f"{name}.comments is longer than {MAX_SPIRIT_COMMENT_CHARS} chars")

    _attr, team_number = SPIRIT_TARGETS[name]
    # `_spirit_scores` refuses a match without both teams before calling us.
    team_id = match.team_1_id if team_number == 1 else match.team_2_id
    assert team_id is not None  # noqa: S101 — guaranteed by the caller
    nominations: dict[str, str | None] = {}
    for key in ("mvp_id", "msp_id"):
        raw = block.get(key)
        if raw in (None, ""):
            nominations[key] = None
            continue
        if name.endswith("_self"):
            raise ProposalApplyError(f"{name} cannot carry {key}; MVP/MSP go on the received block")
        if not Registration.objects.filter(
            event=match.tournament.event, team_id=team_id, player_id=int(str(raw))
        ).exists():
            # create_spirit_scores does a bare .get() with no roster check, so an id
            # from another team would silently nominate a stranger.
            raise ProposalApplyError(
                f"{name}.{key}: player {raw} is not on that team's roster for this event"
            )
        nominations[key] = str(raw)

    return SpiritScoreUpdateSchema(
        **{component: block[component] for component in SPIRIT_COMPONENTS},
        mvp_id=nominations["mvp_id"],
        msp_id=nominations["msp_id"],
        comments=comments,
    )


def _write_spirit_block(match: Match, attr: str, score: SpiritScoreUpdateSchema) -> None:
    """Record one spirit block, reusing the row already on the match if there is one.

    `create_spirit_scores` always inserts. Pointing the match at a fresh row would
    drop the FK to whatever a captain submitted through
    `/match/<id>/submit-spirit-score`, leaving that row in the table with nothing
    referencing it, so a re-entry updates in place instead.
    """
    existing = getattr(match, attr)
    if existing is None:
        setattr(match, attr, create_spirit_scores(score, False))
        return

    for component in SPIRIT_COMPONENTS:
        setattr(existing, component, getattr(score, component))
    existing.total = sum(getattr(score, component) for component in SPIRIT_COMPONENTS)
    existing.comments = score.comments or None
    # UC tournaments are refused above, so only the v2 (Player) nominations apply.
    existing.mvp_v2_id = int(score.mvp_id) if score.mvp_id else None
    existing.msp_v2_id = int(score.msp_id) if score.msp_id else None
    existing.save()


def _spirit_scores(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    if tournament.use_uc_registrations:
        raise ProposalApplyError(
            "This tournament uses Ultimate Central registrations; enter spirit scores in "
            "Classic Tournament Manager instead"
        )
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    if match.team_1_id is None or match.team_2_id is None:
        raise ProposalApplyError(f"Match {match.id} has no teams yet")

    given: dict[str, dict[str, Any]] = {
        name: payload[name] for name in SPIRIT_TARGETS if payload.get(name)
    }
    if not given:
        raise ProposalApplyError("No spirit blocks in this proposal")

    for name, block in given.items():
        attr, _team = SPIRIT_TARGETS[name]
        _write_spirit_block(match, attr, _spirit_block(match, name, block))
    match.save()
    update_tournament_spirit_rankings(tournament)

    # The ranking only counts a match for a team when both its received and self
    # blocks exist, so a partial entry moves nothing — say so rather than implying
    # the table updated.
    counted = [
        team
        for team, blocks in (
            ("team_1", ("team_1_received", "team_1_self")),
            ("team_2", ("team_2_received", "team_2_self")),
        )
        if all(getattr(match, SPIRIT_TARGETS[b][0]) is not None for b in blocks)
    ]
    return {"match_id": match.id, "blocks": sorted(given), "counted_towards_ranking": counted}


def _delete_stage(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    stage_kind = str(payload.get("stage", ""))
    if stage_kind not in STAGE_MODELS:
        raise ProposalApplyError(f"Unknown stage kind: {stage_kind}")
    # The Match field name comes from the same map the tools read, so the stage
    # kinds the model may propose and the ones this can apply cannot drift apart.
    model, match_field = STAGE_MODELS[stage_kind], STAGE_FIELDS[stage_kind]
    stage = model.objects.get(id=payload["stage_id"], tournament=tournament)

    matches = Match.objects.filter(tournament=tournament, **{match_field: stage})
    if matches.filter(status=Match.Status.COMPLETED).exists():
        raise ProposalApplyError(
            "This stage has completed matches — deleting it would leave their results "
            "in the standings with nothing behind them"
        )
    if stage_kind in ("pool", "swiss") and tournament.status in (
        Tournament.Status.LIVE,
        Tournament.Status.COMPLETED,
    ):
        raise ProposalApplyError(
            "Pools and Swiss groups cannot be deleted once the tournament has started"
        )
    if stage_kind in ("pool", "swiss", "cross_pool") and any(
        int(team_id or 0) > 0
        for bracket in Bracket.objects.filter(tournament=tournament)
        for team_id in (bracket.initial_seeding or {}).values()
    ):
        # A downstream bracket already holds real teams, which can only have come
        # from this stage finishing. Deleting it now strands them.
        raise ProposalApplyError(
            "A bracket has already been seeded from this stage — rebuilding now would "
            "leave the bracket pointing at teams with no path into it"
        )

    deleted = matches.count()
    stage.delete()
    return {"stage": stage_kind, "deleted_matches": deleted}


def _start_tournament(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    begin_tournament(tournament)
    return {"status": tournament.status}


def _generate_fixtures(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    populate_fixtures(tournament.id)
    return {"message": "Fixtures populated"}


def _full_setup(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    pool_defs = payload.get("pool_defs") or []
    swiss_defs = payload.get("swiss_defs") or []
    fmt = str(payload.get("format") or "").lower()
    if fmt == "pools" and swiss_defs:
        raise ProposalApplyError("format=pools cannot create Swiss groups")
    if fmt == "swiss" and pool_defs:
        raise ProposalApplyError("format=swiss cannot create pools")

    created: dict[str, Any] = {"pools": [], "swiss": [], "brackets": []}
    for i, pool_def in enumerate(pool_defs):
        created["pools"].append(
            _create_pool(
                tournament,
                {
                    "name": canonical_stage_name(pool_def.get("name"), chr(ord("A") + i)),
                    "sequence_number": pool_def.get("sequence_number") or (i + 1),
                    "seeding": pool_def["seeding"],
                },
            )
        )
    for i, swiss_def in enumerate(swiss_defs):
        created["swiss"].append(
            _create_swiss(
                tournament,
                {
                    "name": canonical_stage_name(swiss_def.get("name"), chr(ord("A") + i)),
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


Applier = Callable[[Tournament, dict[str, Any]], dict[str, Any]]

_APPLIERS: dict[str, Applier] = {
    "propose_create_pool": _create_pool,
    "propose_pool_stage": _create_pool_stage,
    "propose_create_swiss_round": _create_swiss,
    "propose_create_cross_pool": _create_cross_pool,
    "propose_create_bracket": _create_bracket,
    "propose_create_position_pool": _create_position_pool,
    "propose_create_field": _create_field,
    "propose_update_field": _update_field,
    "propose_delete_field": _delete_field,
    "propose_create_cross_pool_matches": _create_cross_pool_matches,
    "propose_update_seeding": _update_seeding,
    "propose_update_match": _update_match,
    "propose_update_match_seeds": _update_match_seeds,
    "propose_delete_match": _delete_match,
    "propose_bulk_schedule": _bulk_schedule,
    # These produce the same assignment payload; recording them under their own
    # names keeps the tool that was actually called visible in proposal history.
    "propose_recommended_schedule": _bulk_schedule,
    "propose_shift_schedule": _bulk_schedule,
    "propose_match_score": _match_score,
    "propose_spirit_scores": _spirit_scores,
    "propose_delete_stage": _delete_stage,
    "propose_start_tournament": _start_tournament,
    "propose_generate_fixtures": _generate_fixtures,
    "propose_full_setup": _full_setup,
}
