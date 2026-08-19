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
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
    populate_fixtures,
    update_match_score_and_results,
    update_tournament_seeding,
    update_tournament_spirit_rankings,
)
from server.tournament.utils import start_tournament as begin_tournament
from server.tournament_agent.models import AgentProposal, ProposalStatus
from server.tournament_agent.tools import STAGE_FIELDS, STAGE_MODELS


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


def _readable(exc: Exception) -> str:
    """Turn a domain/database failure into something staff can act on."""
    if isinstance(exc, ObjectDoesNotExist):
        model = type(exc).__qualname__.removesuffix(".DoesNotExist")
        return f"{model} no longer exists — the tournament changed since this was proposed"
    if isinstance(exc, IntegrityError):
        return f"The database rejected the change: {exc}"
    if isinstance(exc, KeyError):
        return f"The proposal is missing {exc}"
    return str(exc)


def apply_proposal(proposal: AgentProposal) -> dict[str, Any]:
    if proposal.status == ProposalStatus.EXPIRED:
        # Two ways to get here — a newer plan from the same tool replaced this one,
        # or the conversation was cleared. Say what to do rather than just the status.
        raise ProposalApplyError(
            "This plan is no longer current — it was replaced by a newer one, or the "
            "conversation was cleared. Ask the agent again to get a fresh proposal."
        )
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(f"Proposal is {proposal.status}, not pending")

    apply_fn = _APPLIERS.get(proposal.tool_name)
    if apply_fn is None:
        raise ProposalApplyError(f"Unsupported proposal tool: {proposal.tool_name}")

    try:
        # Every applier below writes more than one row; without this a failure
        # part-way leaves the tournament half-changed and the proposal pending.
        with transaction.atomic():
            result = apply_fn(proposal.session.tournament, proposal.payload or {})
            proposal.status = ProposalStatus.CONFIRMED
            proposal.resolved_at = timezone.now()
            proposal.save(update_fields=["status", "resolved_at"])
    except ProposalApplyError:
        raise
    except (
        ObjectDoesNotExist,
        IntegrityError,
        DjangoValidationError,
        ValueError,
        KeyError,
    ) as exc:
        raise ProposalApplyError(_readable(exc)) from exc

    return result


def reject_proposal(proposal: AgentProposal) -> None:
    if proposal.status != ProposalStatus.PENDING:
        raise ProposalApplyError(f"Proposal is {proposal.status}, not pending")
    proposal.status = ProposalStatus.REJECTED
    proposal.resolved_at = timezone.now()
    proposal.save(update_fields=["status", "resolved_at"])


def _create_pool(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    pool = build_pool(
        tournament,
        name=str(payload["name"]),
        sequence_number=int(payload["sequence_number"]),
        seeding=list(payload["seeding"]),
    )
    return {"pool_id": pool.id, "name": pool.name}


def _create_swiss(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    swiss_round = build_swiss_round(
        tournament,
        name=str(payload["name"]),
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
        name=str(payload["name"]),
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


def _update_match(tournament: Tournament, payload: dict[str, Any]) -> dict[str, Any]:
    match = Match.objects.get(id=payload["match_id"], tournament=tournament)
    _set_slot(
        tournament,
        match,
        time=payload.get("time"),
        field_id=payload.get("field_id"),
        duration_mins=payload.get("duration_mins"),
    )
    return {"match_id": match.id}


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
    updated = []
    for row in payload.get("assignments") or []:
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
                    "name": pool_def.get("name") or chr(ord("A") + i),
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


Applier = Callable[[Tournament, dict[str, Any]], dict[str, Any]]

_APPLIERS: dict[str, Applier] = {
    "propose_create_pool": _create_pool,
    "propose_create_swiss_round": _create_swiss,
    "propose_create_cross_pool": _create_cross_pool,
    "propose_create_bracket": _create_bracket,
    "propose_create_position_pool": _create_position_pool,
    "propose_create_field": _create_field,
    "propose_create_cross_pool_matches": _create_cross_pool_matches,
    "propose_update_seeding": _update_seeding,
    "propose_update_match": _update_match,
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
