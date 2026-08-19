import contextlib
import datetime
import os
from collections import Counter
from collections.abc import Callable
from typing import Any, cast

from django.db import transaction
from django.db.models import Q

from server.core.models import Player, Team, UCPerson, User
from server.series.models import SeriesRegistration
from server.tournament.models import Event
from server.types import message_response, validation_error_dict
from server.utils import ordinal_suffix

from .models import (
    Bracket,
    CrossPool,
    Match,
    Pool,
    PositionPool,
    Registration,
    SpiritScore,
    SwissRound,
    Tournament,
    UCRegistration,
)
from .schema import SpiritScoreUpdateSchema

ROLES_ELIGIBLE_TO_SUBMIT_SCORES = [
    "admin",
    "captain",
    "spirit captain",
    "coach",
    "assistant coach",
    "manager",
]
PLAYER_ROLE = "player"


# Exported Functions ####################


def update_tournament_seeding(
    tournament: Tournament, seeding: dict[int, int]
) -> tuple[bool, message_response | None]:
    """Validate and apply a new tournament seeding before the tournament starts.

    Pools and Swiss groups snapshot seed -> team_id (and per-team results) at
    creation time. Re-syncing those snapshots here lets staff re-seed freely
    at any point before the tournament starts, without having to delete and
    recreate the whole structure. Matches only hold placeholder seeds until
    the tournament starts, so they need no update.
    """
    if tournament.status in (Tournament.Status.LIVE, Tournament.Status.COMPLETED):
        return False, {
            "message": "Cannot update seeding after the tournament has started. "
            "Match results drive the current seeding once the tournament is live."
        }

    valid_seeds_and_teams, errors = validate_seeds_and_teams(tournament, seeding)
    if not valid_seeds_and_teams:
        message = "Cannot update standings, due to following errors: \n"
        message += "\n".join(f"{key}: {value}" for key, value in errors.items())
        return False, {"message": message}

    with transaction.atomic():
        tournament.initial_seeding = dict(sorted(seeding.items()))
        tournament.current_seeding = dict(sorted(seeding.items()))
        tournament.save()

        seed_to_team = {int(seed): team_id for seed, team_id in seeding.items()}

        for pool in Pool.objects.filter(tournament=tournament):
            new_seeding: dict[int, int] = {}
            new_results: dict[int, dict[str, int]] = {}
            for i, seed in enumerate(sorted(map(int, pool.initial_seeding.keys()))):
                team_id = seed_to_team[seed]
                new_seeding[seed] = team_id
                new_results[team_id] = {
                    "rank": i + 1,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "GF": 0,
                    "GA": 0,
                }
            pool.initial_seeding = new_seeding
            pool.results = new_results
            pool.save()

        for swiss_round in SwissRound.objects.filter(tournament=tournament):
            new_swiss_seeding: dict[int, int] = {}
            new_swiss_results: dict[str, dict[str, int]] = {}
            for i, seed in enumerate(sorted(map(int, swiss_round.initial_seeding.keys()))):
                team_id = seed_to_team[seed]
                new_swiss_seeding[seed] = team_id
                new_swiss_results[str(team_id)] = {
                    "rank": i + 1,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "GF": 0,
                    "GA": 0,
                    "opp_strength": 0,
                }
            swiss_round.initial_seeding = new_swiss_seeding
            swiss_round.results = new_swiss_results
            swiss_round.save()

    return True, None


def create_pool_matches(tournament: Tournament, pool: Pool) -> None:
    pool_seeding_list = list(map(int, pool.initial_seeding.keys()))

    for i, seed_x in enumerate(pool_seeding_list):
        for j, seed_y in enumerate(pool_seeding_list[i + 1 :], i + 1):
            match = Match(
                name=f"{pool.name}{i + 1} vs {pool.name}{j + 1}",
                tournament=tournament,
                pool=pool,
                sequence_number=1,
                placeholder_seed_1=seed_x,
                placeholder_seed_2=seed_y,
            )

            match.save()


def create_bracket_matches(tournament: Tournament, bracket: Bracket) -> None:
    seeds = sorted(map(int, bracket.initial_seeding.keys()))
    start, end = seeds[0], seeds[-1]
    if ((end - start) + 1) % 2 == 0:
        create_bracket_sequence_matches(tournament, bracket, start, end, 1)


def create_position_pool_matches(tournament: Tournament, position_pool: PositionPool) -> None:
    position_pool_seeding_list = list(map(int, position_pool.initial_seeding.keys()))

    for i, seed_x in enumerate(position_pool_seeding_list):
        for j, seed_y in enumerate(position_pool_seeding_list[i + 1 :], i + 1):
            match = Match(
                name=f"{position_pool.name}{i + 1} vs {position_pool.name}{j + 1}",
                tournament=tournament,
                position_pool=position_pool,
                sequence_number=1,
                placeholder_seed_1=seed_x,
                placeholder_seed_2=seed_y,
            )

            match.save()


# Stage builders ####################
#
# Single source of truth for creating a stage and its matches. Both the staff API
# and the tournament agent's proposal apply path call these, so the two can never
# drift apart on seeding shape, results shape or validation. They raise ValueError
# with a staff-readable message; callers translate that to their own error type.


def _validation_message(prefix: str, errors: validation_error_dict) -> str:
    details = "\n".join(f"{key}: {value}" for key, value in errors.items())
    return f"{prefix}, due to following errors: \n{details}"


def _team_id_for_seed(tournament: Tournament, seed: int) -> int:
    # Seeds come back from the database as strings, but the m2m signal that rebuilds
    # seeding leaves int keys on the in-memory instance, so accept either.
    seeding = tournament.initial_seeding or {}
    team_id = seeding.get(str(seed), seeding.get(seed))
    if team_id is None:
        raise ValueError(f"Seed {seed} is not in the tournament seeding")
    return int(team_id)


def _seeded_results(
    tournament: Tournament, seeding: list[int], *, with_opp_strength: bool = False
) -> tuple[dict[int, int], dict[str, dict[str, int]]]:
    """Build (seed -> team_id, team_id -> zeroed standings row) in seeding order."""
    stage_seeding: dict[int, int] = {}
    results: dict[str, dict[str, int]] = {}
    for rank, seed in enumerate(seeding, start=1):
        team_id = _team_id_for_seed(tournament, seed)
        stage_seeding[seed] = team_id
        results[str(team_id)] = {
            "rank": rank,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "GF": 0,  # Goals For
            "GA": 0,  # Goals Against
            **({"opp_strength": 0} if with_opp_strength else {}),
        }
    return dict(sorted(stage_seeding.items())), results


def build_pool(
    tournament: Tournament, *, name: str, sequence_number: int, seeding: list[int]
) -> Pool:
    valid, errors = validate_new_pool(tournament=tournament, new_pool=set(seeding))
    if not valid:
        raise ValueError(_validation_message("Cannot create pools", errors))

    pool_seeding, results = _seeded_results(tournament, seeding)
    pool = Pool.objects.create(
        tournament=tournament,
        name=name,
        sequence_number=sequence_number,
        initial_seeding=pool_seeding,
        results=results,
    )
    create_pool_matches(tournament, pool)
    return pool


def build_swiss_round(
    tournament: Tournament,
    *,
    name: str,
    sequence_number: int,
    seeding: list[int],
    num_rounds: int,
) -> SwissRound:
    min_swiss_teams = 2
    if len(seeding) < min_swiss_teams:
        raise ValueError("Need at least 2 teams for a swiss group")
    if num_rounds < 1:
        raise ValueError("Number of rounds must be at least 1")

    valid, errors = validate_new_pool(tournament=tournament, new_pool=set(seeding))
    if not valid:
        raise ValueError(_validation_message("Cannot create swiss group", errors))

    swiss_seeding, results = _seeded_results(tournament, seeding, with_opp_strength=True)
    swiss_round = SwissRound.objects.create(
        tournament=tournament,
        name=name,
        sequence_number=sequence_number,
        num_rounds=num_rounds,
        # Round 1 exists as soon as the group does. Leaving this at 0 would make
        # populate_fixtures skip the group forever, so it must never be omitted.
        current_round=1,
        initial_seeding=swiss_seeding,
        results=results,
        byes={},
    )
    create_swiss_round_matches(tournament, swiss_round)
    return swiss_round


def build_bracket(tournament: Tournament, *, name: str, sequence_number: int) -> Bracket:
    valid_name, name_error = validate_bracket_name(name)
    if not valid_name:
        raise ValueError((name_error or {}).get("message", "Invalid bracket name"))

    start, end = (int(part) for part in name.split("-"))
    seeding = {seed: 0 for seed in range(start, end + 1)}
    bracket = Bracket.objects.create(
        tournament=tournament,
        name=name,
        sequence_number=sequence_number,
        initial_seeding=dict(seeding),
        current_seeding=dict(seeding),
    )
    create_bracket_matches(tournament, bracket)
    return bracket


def build_position_pool(
    tournament: Tournament, *, name: str, sequence_number: int, seeding: list[int]
) -> PositionPool:
    # Seeds are placeholders until the feeding stage completes, and `results` is
    # keyed by team id — populate_fixtures fills both. Seeding it here with seed
    # keys would leave two incompatible key sets in one dict.
    position_pool = PositionPool.objects.create(
        tournament=tournament,
        name=name,
        sequence_number=sequence_number,
        initial_seeding={seed: 0 for seed in sorted(seeding)},
        results={},
    )
    create_position_pool_matches(tournament, position_pool)
    return position_pool


def start_tournament(tournament: Tournament) -> None:
    """Assign teams into pool and Swiss round-1 matches, and go live."""
    if tournament.status in (Tournament.Status.LIVE, Tournament.Status.COMPLETED):
        # Re-running would reset completed matches back to Scheduled while keeping
        # their scores, leaving standings that no stage can be derived from again.
        raise ValueError("Tournament has already been started")

    for match in Match.objects.filter(tournament=tournament).exclude(pool__isnull=True):
        match.team_1 = Team.objects.get(id=_team_id_for_seed(tournament, match.placeholder_seed_1))
        match.team_2 = Team.objects.get(id=_team_id_for_seed(tournament, match.placeholder_seed_2))
        match.status = Match.Status.SCHEDULED
        match.save()

    for swiss_round in SwissRound.objects.filter(tournament=tournament):
        assign_swiss_round_teams(tournament, swiss_round, 1)

    tournament.status = Tournament.Status.LIVE
    tournament.save()


BYE_SCORE = 15


def select_bye_team(swiss_round: SwissRound) -> int:
    """Select lowest-ranked team that hasn't had a bye yet.

    Uses the same Swiss standings logic as the rest of the system:
    - Prefer the existing ``rank`` field when present (already computed via
      points → H2H → opponent strength → goal difference).
    - Fall back to a points/GD/GF sort if ranks have not yet been assigned.
    """
    teams_with_byes = set(swiss_round.byes.values())
    results = {int(tid): stats for tid, stats in swiss_round.results.items()}

    has_rank = bool(results) and "rank" in next(iter(results.values()))

    if has_rank:
        # Lower rank number = better; we want the worst available team,
        # so iterate from highest rank value downward.
        standings = sorted(results.items(), key=lambda item: item[1]["rank"], reverse=True)
    else:
        # Fallback: sort by points, then GD, then GF (ascending — worst first)
        standings = sorted(
            results.items(),
            key=lambda item: (
                item[1]["wins"] * 2 + item[1].get("draws", 0),
                item[1]["GF"] - item[1]["GA"],
                item[1]["GF"],
            ),
        )

    for tid, _ in standings:
        if tid not in teams_with_byes:
            return tid

    # Fallback: if all teams have had byes, just return the worst by standings.
    return standings[0][0]


def apply_bye(swiss_round: SwissRound, team_id: int, round_number: int) -> None:
    """Apply bye: +1 win, +BYE_SCORE GF, re-rank, update seeding."""
    results = {int(k): v for k, v in swiss_round.results.items()}

    results[team_id]["wins"] += 1
    results[team_id]["GF"] += BYE_SCORE

    # Re-rank all teams by points (win=2, draw=1) with Swiss tiebreakers
    pool_seeding_list = sorted(map(int, swiss_round.initial_seeding.keys()))
    tournament = swiss_round.tournament
    tournament_seeding = {int(k): v for k, v in tournament.current_seeding.items()}

    results, tournament_seeding = recompute_swiss_ranks(
        swiss_round, results, pool_seeding_list, tournament_seeding
    )

    # Compute and store opponent strength (sum of opponents' points)
    all_swiss_matches = Match.objects.filter(swiss_round=swiss_round, status=Match.Status.COMPLETED)
    opp_strength: dict[int, int] = {tid: 0 for tid in results}
    for m in all_swiss_matches:
        if m.team_1 and m.team_2:
            t1, t2 = m.team_1.id, m.team_2.id
            if t1 in opp_strength:
                opp_stats = results.get(t2, {})
                opp_strength[t1] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
            if t2 in opp_strength:
                opp_stats = results.get(t1, {})
                opp_strength[t2] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
    for tid in results:
        results[tid]["opp_strength"] = opp_strength.get(tid, 0)

    swiss_round.results = results
    byes = dict(swiss_round.byes)
    byes[str(round_number)] = team_id
    swiss_round.byes = byes
    swiss_round.save()

    tournament.current_seeding = tournament_seeding
    tournament.save()


def create_swiss_round_matches(tournament: Tournament, swiss_round: SwissRound) -> None:
    """Create all match slots for all Swiss rounds upfront.

    Round 1: Real pairings (seed 1 vs seed N, seed 2 vs seed N-1, etc.)
    Rounds 2+: Placeholder match slots with arbitrary seed pairs.
    For odd team counts, last seed gets bye in R1 and is excluded from pairings.
    """
    seeds = sorted(map(int, swiss_round.initial_seeding.keys()))
    n = len(seeds)
    num_matches_per_round = n // 2
    is_odd = n % 2 != 0

    for round_num in range(1, swiss_round.num_rounds + 1):
        if round_num == 1:
            if is_odd:
                # Exclude last seed (bye), pair remaining n-1 seeds
                active_seeds = seeds[:-1]
                active_n = len(active_seeds)
                pairs = [
                    (active_seeds[i], active_seeds[active_n - 1 - i]) for i in range(active_n // 2)
                ]
            else:
                pairs = [(seeds[i], seeds[n - 1 - i]) for i in range(num_matches_per_round)]
        else:
            # Placeholder slots using first n-1 seeds (even count) for odd, or all for even
            active_seeds = seeds[:-1] if is_odd else seeds
            pairs = [
                (active_seeds[i * 2], active_seeds[i * 2 + 1]) for i in range(num_matches_per_round)
            ]

        for match_num, (seed_1, seed_2) in enumerate(pairs, 1):
            Match(
                name=f"Swiss {swiss_round.name} R{round_num} M{match_num}",
                tournament=tournament,
                swiss_round=swiss_round,
                sequence_number=round_num,
                placeholder_seed_1=seed_1,
                placeholder_seed_2=seed_2,
            ).save()


def assign_swiss_round_teams(
    tournament: Tournament, swiss_round: SwissRound, round_number: int
) -> None:
    """Assign teams to Swiss round match slots.

    Round 1: Assigns based on initial seeding placeholder seeds.
    Rounds 2+: Runs pairing algorithm and assigns teams to pre-created slots.
    For odd team counts, applies bye before assigning matches.
    """
    teams_by_id = {team.id: team for team in tournament.teams.all()}
    is_odd = len(teams_by_id) % 2 != 0

    # Apply bye for odd team counts
    bye_team_id: int | None = None
    if is_odd:
        if round_number == 1:
            # Last seed gets bye in round 1
            last_seed = max(int(s) for s in swiss_round.initial_seeding)
            bye_team_id = int(swiss_round.initial_seeding[str(last_seed)])
        else:
            bye_team_id = select_bye_team(swiss_round)
        apply_bye(swiss_round, bye_team_id, round_number)

    round_matches = list(
        Match.objects.filter(swiss_round=swiss_round, sequence_number=round_number).order_by("id")
    )

    if round_number == 1:
        # Round 1 match slots already have correct placeholder seeds
        for match in round_matches:
            team_1_id = int(swiss_round.initial_seeding[str(match.placeholder_seed_1)])
            team_2_id = int(swiss_round.initial_seeding[str(match.placeholder_seed_2)])
            match.team_1 = teams_by_id[team_1_id]
            match.team_2 = teams_by_id[team_2_id]
            match.status = Match.Status.SCHEDULED
            match.save()
    else:
        # Generate pairings based on current standings, excluding bye team
        pairings = generate_swiss_pairings(swiss_round, exclude_team_id=bye_team_id)

        # Build team_id -> current rank map from results
        team_rank: dict[int, int] = swiss_team_rank_map(swiss_round.results)

        for i, (team_1_id, team_2_id) in enumerate(pairings):
            if i < len(round_matches):
                match = round_matches[i]
                match.team_1 = teams_by_id[team_1_id]
                match.team_2 = teams_by_id[team_2_id]
                match.placeholder_seed_1 = team_rank[team_1_id]
                match.placeholder_seed_2 = team_rank[team_2_id]
                match.status = Match.Status.SCHEDULED
                match.save()


def reorder_swiss_round_matches(swiss_round: SwissRound, round_number: int) -> None:
    """Reassign time/field slots within a Swiss round to avoid back-to-back matches.

    Teams that played most recently are scheduled in the latest available slots.
    Only operates within the current round; pairings are never changed.
    """
    round_matches = list(
        Match.objects.filter(swiss_round=swiss_round, sequence_number=round_number)
        .select_related("team_1", "team_2", "field")
        .order_by("id")
    )

    # Only proceed if there are scheduled matches with times
    scheduled_matches = [m for m in round_matches if m.time is not None]
    if len(scheduled_matches) <= 1:
        return

    unique_times = {m.time for m in scheduled_matches}
    if len(unique_times) <= 1:
        return

    # Gather all team IDs in this round
    team_ids_in_round: set[int] = set()
    for m in round_matches:
        if m.team_1_id:
            team_ids_in_round.add(m.team_1_id)
        if m.team_2_id:
            team_ids_in_round.add(m.team_2_id)

    if not team_ids_in_round:
        return

    # Find each team's most recent match time before this round
    team_last_played: dict[int, datetime.datetime] = {}
    for team_id in team_ids_in_round:
        last_match = (
            Match.objects.filter(
                Q(team_1_id=team_id) | Q(team_2_id=team_id),
                tournament=swiss_round.tournament,
            )
            .exclude(swiss_round=swiss_round, sequence_number=round_number)
            .filter(time__isnull=False)
            .order_by("-time")
            .first()
        )
        if last_match and last_match.time:
            team_last_played[team_id] = last_match.time

    min_dt = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    def _last_played(team_id: int | None) -> datetime.datetime:
        if team_id is None:
            return min_dt
        return team_last_played.get(team_id, min_dt)

    # Compute sort key for each scheduled match: the latest last-played time of its two teams
    match_sort_key: list[tuple[datetime.datetime, Match]] = []
    for m in scheduled_matches:
        latest = max(_last_played(m.team_1_id), _last_played(m.team_2_id))
        match_sort_key.append((latest, m))

    # Sort by latest last-played descending (least rested first)
    match_sort_key.sort(key=lambda x: x[0], reverse=True)

    # Collect slots (time, field_id) from this round, sort by time descending (latest first).
    # `scheduled_matches` is pre-filtered to non-null times, so the cast is safe.
    slots: list[tuple[datetime.datetime, int | None]] = [
        (cast(datetime.datetime, m.time), m.field_id) for m in scheduled_matches
    ]
    slots.sort(key=lambda x: x[0], reverse=True)

    # Reassign: least-rested match gets the latest slot.
    # To avoid UNIQUE constraint violations when two matches swap time+field,
    # we first clear time/field for all matches that need updating, then set
    # the final values.
    matches_to_update: list[tuple[Match, datetime.datetime, int | None]] = []
    for (_, match), (new_time, new_field_id) in zip(match_sort_key, slots, strict=True):
        if match.time != new_time or match.field_id != new_field_id:
            matches_to_update.append((match, new_time, new_field_id))

    if not matches_to_update:
        return

    # Phase 1: clear time/field
    for match, _, _ in matches_to_update:
        match.time = None
        match.field = None
        match.save()

    # Phase 2: set final time/field
    for match, new_time, new_field_id in matches_to_update:
        match.time = new_time
        match.field_id = new_field_id
        match.save()


def _backtrack_pair(
    team_ids: list[int],
    played_pairs: set[frozenset[int]],
    paired: set[int],
    pairs: list[tuple[int, int]],
    index: int,
) -> bool:
    """Recursively try to pair all teams without rematches.

    Preserves standings order: higher-ranked teams get first pick of
    closest-ranked available opponent. Backtracks if a choice leads
    to a dead end for later teams.
    """
    # Skip already-paired teams
    while index < len(team_ids) and team_ids[index] in paired:
        index += 1
    if index >= len(team_ids):
        return True  # All teams paired successfully

    tid = team_ids[index]
    for j in range(index + 1, len(team_ids)):
        candidate = team_ids[j]
        if candidate in paired:
            continue
        if frozenset([tid, candidate]) in played_pairs:
            continue
        # Try this pairing
        paired.add(tid)
        paired.add(candidate)
        pairs.append((tid, candidate))
        if _backtrack_pair(team_ids, played_pairs, paired, pairs, index + 1):
            return True
        # Undo and try next candidate
        paired.discard(tid)
        paired.discard(candidate)
        pairs.pop()
    return False


def generate_swiss_pairings(
    swiss_round: SwissRound, exclude_team_id: int | None = None
) -> list[tuple[int, int]]:
    """Generate Swiss pairings based on current standings, avoiding rematches.

    Uses backtracking to find a valid complete matching without rematches.
    Teams are sorted by standings and higher-ranked teams get priority
    in choosing closest-ranked opponents. Falls back to greedy pairing
    with rematches only if no valid matching exists.
    """
    results = swiss_round.results

    # Build set of already-played matchups and compute opponent strength
    played_matches = list(
        Match.objects.filter(swiss_round=swiss_round)
        .exclude(team_1__isnull=True)
        .exclude(team_2__isnull=True)
        .filter(status=Match.Status.COMPLETED)
    )
    played_pairs: set[frozenset[int]] = set()
    opp_strength: dict[int, int] = {int(tid): 0 for tid in results}
    for m in played_matches:
        if m.team_1 and m.team_2:
            played_pairs.add(frozenset([m.team_1.id, m.team_2.id]))
            t1, t2 = m.team_1.id, m.team_2.id
            t1_stats = results.get(str(t1), results.get(t1, {}))
            t2_stats = results.get(str(t2), results.get(t2, {}))
            if t1 in opp_strength:
                opp_strength[t1] += t2_stats.get("wins", 0) * 2 + t2_stats.get("draws", 0)
            if t2 in opp_strength:
                opp_strength[t2] += t1_stats.get("wins", 0) * 2 + t1_stats.get("draws", 0)

    standings = sorted(
        [
            (int(team_id), stats)
            for team_id, stats in results.items()
            if int(team_id) != exclude_team_id
        ],
        key=lambda item: (
            item[1]["wins"] * 2 + item[1].get("draws", 0),  # Points: win=2, draw=1
            opp_strength.get(item[0], 0),  # Opponent strength: higher = faced stronger
            item[1]["GF"] - item[1]["GA"],
            item[1]["GF"],
        ),
        reverse=True,
    )

    team_ids = [team_id for team_id, _ in standings]
    paired: set[int] = set()
    pairs: list[tuple[int, int]] = []

    # Try backtracking to find a complete no-rematch matching
    if _backtrack_pair(team_ids, played_pairs, paired, pairs, 0):
        return pairs

    # Fallback: greedy pairing allowing rematches (should rarely happen)
    paired.clear()
    pairs.clear()
    for i, tid in enumerate(team_ids):
        if tid in paired:
            continue
        for j in range(i + 1, len(team_ids)):
            candidate = team_ids[j]
            if candidate in paired:
                continue
            if frozenset([tid, candidate]) not in played_pairs:
                pairs.append((tid, candidate))
                paired.add(tid)
                paired.add(candidate)
                break
        else:
            for j in range(i + 1, len(team_ids)):
                candidate = team_ids[j]
                if candidate not in paired:
                    pairs.append((tid, candidate))
                    paired.add(tid)
                    paired.add(candidate)
                    break

    return pairs


def sort_tied_teams(
    tied_teams: list[dict[str, int]],
    tournament_id: int,
    stage: Pool | PositionPool | None = None,
) -> list[dict[str, int]]:
    """Order teams tied on pool wins, following the WFDF tie-break procedure.

    Criteria, in order of precedence:
    1. Games won counting only games between tied teams
    2. Goal difference counting only games between tied teams
    3. Goal difference counting all pool games
    4. Goals scored counting only games between tied teams
    5. Goals scored counting all pool games

    Per WFDF, whenever a criterion separates the tied group into smaller
    groups, the procedure restarts at criterion 1 within each remaining
    tied sub-group (head-to-head stats are recomputed among only those
    teams). Only games from the same stage (this pool / position pool)
    count towards the head-to-head criteria.
    """
    if len(tied_teams) <= 1:
        return list(tied_teams)

    team_stats: dict[int, dict[str, int]] = {
        team["id"]: {"wins": 0, "gd": 0, "gf": 0} for team in tied_teams
    }

    # Get matches between tied teams, restricted to this stage's games
    team_ids = [team["id"] for team in tied_teams]
    matches = Match.objects.filter(
        tournament_id=tournament_id, status=Match.Status.COMPLETED
    ).filter(Q(team_1__id__in=team_ids, team_2__id__in=team_ids))
    if isinstance(stage, Pool):
        matches = matches.filter(pool=stage)
    elif isinstance(stage, PositionPool):
        matches = matches.filter(position_pool=stage)

    # Calculate head-to-head stats
    for match in matches:
        if match.team_1 is None or match.team_2 is None:
            continue

        # Update wins
        if match.score_team_1 > match.score_team_2:
            team_stats[match.team_1.id]["wins"] += 1
        elif match.score_team_2 > match.score_team_1:
            team_stats[match.team_2.id]["wins"] += 1

        # Update goal difference and goals for
        team_stats[match.team_1.id]["gd"] += match.score_team_1 - match.score_team_2
        team_stats[match.team_2.id]["gd"] += match.score_team_2 - match.score_team_1
        team_stats[match.team_1.id]["gf"] += match.score_team_1
        team_stats[match.team_2.id]["gf"] += match.score_team_2

    def criteria(team: dict[str, int]) -> tuple[int, int, int, int, int]:
        return (
            team_stats[team["id"]]["wins"],  # 1. Head-to-head wins
            team_stats[team["id"]]["gd"],  # 2. Head-to-head goal difference
            team["GF"] - team["GA"],  # 3. Overall goal difference
            team_stats[team["id"]]["gf"],  # 4. Head-to-head goals scored
            team["GF"],  # 5. Overall goals scored
        )

    return _rank_by_criteria_with_restart(
        tied_teams,
        criteria,
        lambda sub_group: sort_tied_teams(sub_group, tournament_id, stage),
    )


def _rank_by_criteria_with_restart(
    tied_teams: list[dict[str, int]],
    criteria: Callable[[dict[str, int]], tuple[int, ...]],
    restart: Callable[[list[dict[str, int]]], list[dict[str, int]]],
) -> list[dict[str, int]]:
    """Apply ordered tie-break criteria with the WFDF restart rule.

    Finds the first criterion that separates the group, orders sub-groups by
    that criterion, then restarts the full procedure within each sub-group
    that is still tied. Returns the teams unchanged when no criterion can
    separate them.
    """
    num_criteria = len(criteria(tied_teams[0]))
    for index in range(num_criteria):
        values = {criteria(team)[index] for team in tied_teams}
        if len(values) == 1:
            continue

        ordered: list[dict[str, int]] = []
        for value in sorted(values, reverse=True):
            sub_group = [team for team in tied_teams if criteria(team)[index] == value]
            if len(sub_group) > 1:
                # Strictly smaller than tied_teams (values has >1 entry),
                # so the restart always terminates.
                sub_group = restart(sub_group)
            ordered.extend(sub_group)
        return ordered

    return list(tied_teams)


def sort_swiss_tied_teams(
    tied_teams: list[dict[str, int]],
    all_results: dict[int, dict[str, int]],
    swiss_round: SwissRound,
) -> list[dict[str, int]]:
    """Swiss tiebreaker for teams with equal points (win=2, draw=1).

    Order of precedence:
    1. Head-to-head wins (between tied teams)
    2. Strength of opponents faced (sum of opponents' points — higher = stronger)
    3. Overall goal difference

    Whenever a criterion separates the tied group, the procedure restarts
    at criterion 1 within each remaining tied sub-group (smaller group
    means different H2H dynamics).
    """
    if len(tied_teams) <= 1:
        return tied_teams

    team_ids = [team["id"] for team in tied_teams]

    # 1. Compute H2H stats between tied teams
    h2h_wins: dict[int, int] = {tid: 0 for tid in team_ids}
    h2h_matches = Match.objects.filter(
        swiss_round=swiss_round, status=Match.Status.COMPLETED
    ).filter(Q(team_1__id__in=team_ids, team_2__id__in=team_ids))
    for m in h2h_matches:
        if m.team_1 and m.team_2:
            if m.score_team_1 > m.score_team_2:
                h2h_wins[m.team_1.id] += 1
            elif m.score_team_2 > m.score_team_1:
                h2h_wins[m.team_2.id] += 1

    # 2. Compute opponent strength: sum of opponents' points (higher = faced stronger opponents)
    opp_strength: dict[int, int] = {tid: 0 for tid in team_ids}
    all_swiss_matches = Match.objects.filter(
        swiss_round=swiss_round, status=Match.Status.COMPLETED
    ).filter(Q(team_1__id__in=team_ids) | Q(team_2__id__in=team_ids))
    for m in all_swiss_matches:
        if m.team_1 and m.team_2:
            if m.team_1.id in opp_strength:
                opp_stats = all_results.get(m.team_2.id, {})
                opp_strength[m.team_1.id] += opp_stats.get("wins", 0) * 2 + opp_stats.get(
                    "draws", 0
                )
            if m.team_2.id in opp_strength:
                opp_stats = all_results.get(m.team_1.id, {})
                opp_strength[m.team_2.id] += opp_stats.get("wins", 0) * 2 + opp_stats.get(
                    "draws", 0
                )

    def criteria(t: dict[str, int]) -> tuple[int, ...]:
        return (
            h2h_wins[t["id"]],  # 1. H2H wins (higher = better)
            opp_strength[t["id"]],  # 2. Opponent strength: higher = faced stronger
            t["GF"] - t["GA"],  # 3. Overall goal difference
        )

    # Whenever a criterion separates the group, restart the procedure within
    # each remaining tied sub-group (H2H is recomputed among only those teams).
    return _rank_by_criteria_with_restart(
        tied_teams,
        criteria,
        lambda sub_group: sort_swiss_tied_teams(sub_group, all_results, swiss_round),
    )


def recompute_swiss_ranks(
    swiss_round: SwissRound,
    results: dict[int, dict[str, int]],
    pool_seeding_list: list[int],
    tournament_seeding: dict[int, int],
) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
    """Assign ranks by points (win=2, draw=1) with Swiss tiebreakers.

    Updates the given tournament seeding map so the group's seeds follow the
    new rank order. This is the single source of truth for Swiss ranking —
    byes, reruns and score updates must all rank teams the same way.
    """
    for tid in results:
        results[tid]["id"] = tid

    points_groups: dict[int, list[dict[str, int]]] = {}
    for result in results.values():
        points = result["wins"] * 2 + result.get("draws", 0)
        points_groups.setdefault(points, []).append(result)

    ranked: list[dict[str, int]] = []
    for points in sorted(points_groups, reverse=True):
        tied = points_groups[points]
        if len(tied) == 1:
            ranked.extend(tied)
        else:
            ranked.extend(sort_swiss_tied_teams(tied, results, swiss_round))

    for i, result in enumerate(ranked):
        results[result["id"]]["rank"] = i + 1
        tournament_seeding[pool_seeding_list[i]] = int(result["id"])

    return results, tournament_seeding


def swiss_team_rank_map(results: dict[Any, dict[str, int]]) -> dict[int, int]:
    """Team id -> current rank, preferring stored ranks over a raw points sort."""
    normalized = {int(tid): stats for tid, stats in results.items()}
    ranks = [stats.get("rank") for stats in normalized.values()]
    if all(isinstance(rank, int) for rank in ranks) and len(set(ranks)) == len(ranks):
        return {tid: stats["rank"] for tid, stats in normalized.items()}

    ranked = sorted(
        normalized.items(),
        key=lambda item: (
            item[1]["wins"] * 2 + item[1].get("draws", 0),
            item[1]["GF"] - item[1]["GA"],
            item[1]["GF"],
        ),
        reverse=True,
    )
    return {tid: i + 1 for i, (tid, _) in enumerate(ranked)}


def get_new_pool_results(
    old_results: dict[int, dict[str, int]],
    match: Match,
    pool_seeding_list: list[int],
    tournament_seeding: dict[int, int],
) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
    if match.team_1 is None or match.team_2 is None:
        return old_results, tournament_seeding

    old_results[match.team_1.id]["GF"] += match.score_team_1
    old_results[match.team_1.id]["GA"] += match.score_team_2

    old_results[match.team_2.id]["GF"] += match.score_team_2
    old_results[match.team_2.id]["GA"] += match.score_team_1

    if match.score_team_1 > match.score_team_2:
        old_results[match.team_1.id]["wins"] += 1
        old_results[match.team_2.id]["losses"] += 1
    elif match.score_team_1 < match.score_team_2:
        old_results[match.team_2.id]["wins"] += 1
        old_results[match.team_1.id]["losses"] += 1
    else:
        old_results[match.team_1.id]["draws"] += 1
        old_results[match.team_2.id]["draws"] += 1

    # Create results list with team IDs
    results_list = []
    for team_id, result in old_results.items():
        result["id"] = team_id
        results_list.append(result)

    # Group teams by number of wins to identify ties
    wins_groups: dict[int, list[dict[str, int]]] = {}
    for result in results_list:
        wins = result["wins"]
        if wins not in wins_groups:
            wins_groups[wins] = []
        wins_groups[wins].append(result)

    # Sort each tied group separately
    ranked_results = []
    for wins in sorted(wins_groups.keys(), reverse=True):
        tied_teams = wins_groups[wins]
        if len(tied_teams) == 1:
            ranked_results.extend(tied_teams)
        else:
            # Sort tied teams using head-to-head criteria within this stage
            stage = match.pool or match.position_pool
            sorted_tied_teams = sort_tied_teams(tied_teams, match.tournament.id, stage)
            ranked_results.extend(sorted_tied_teams)

    new_results = {}
    for i, result in enumerate(ranked_results):
        new_results[result["id"]] = result
        new_results[result["id"]]["rank"] = i + 1
        tournament_seeding[pool_seeding_list[i]] = int(result["id"])

    return new_results, tournament_seeding


def get_new_swiss_results(
    old_results: dict[int, dict[str, int]],
    match: Match,
    pool_seeding_list: list[int],
    tournament_seeding: dict[int, int],
) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
    """Update Swiss round results after a match.

    Uses points system (win=2, draw=1, loss=0) for primary ranking,
    then Swiss-specific tiebreakers for teams with equal points.
    """
    if match.team_1 is None or match.team_2 is None:
        return old_results, tournament_seeding

    old_results[match.team_1.id]["GF"] += match.score_team_1
    old_results[match.team_1.id]["GA"] += match.score_team_2

    old_results[match.team_2.id]["GF"] += match.score_team_2
    old_results[match.team_2.id]["GA"] += match.score_team_1

    if match.score_team_1 > match.score_team_2:
        old_results[match.team_1.id]["wins"] += 1
        old_results[match.team_2.id]["losses"] += 1
    elif match.score_team_1 < match.score_team_2:
        old_results[match.team_2.id]["wins"] += 1
        old_results[match.team_1.id]["losses"] += 1
    else:
        old_results[match.team_1.id]["draws"] += 1
        old_results[match.team_2.id]["draws"] += 1

    # Create results list with team IDs
    results_list = []
    for team_id, result in old_results.items():
        result["id"] = team_id
        results_list.append(result)

    # Group teams by points (win=2, draw=1, loss=0)
    points_groups: dict[int, list[dict[str, int]]] = {}
    for result in results_list:
        points = result["wins"] * 2 + result.get("draws", 0)
        if points not in points_groups:
            points_groups[points] = []
        points_groups[points].append(result)

    # Sort each tied group using Swiss tiebreakers (H2H → OS → GD)
    ranked_results = []
    for points in sorted(points_groups.keys(), reverse=True):
        tied_teams = points_groups[points]
        if len(tied_teams) == 1:
            ranked_results.extend(tied_teams)
        else:
            if match.swiss_round is None:
                raise ValueError("Swiss round must be set for swiss tiebreaker sorting")
            sorted_tied_teams = sort_swiss_tied_teams(tied_teams, old_results, match.swiss_round)
            ranked_results.extend(sorted_tied_teams)

    new_results = {}
    for i, result in enumerate(ranked_results):
        new_results[result["id"]] = result
        new_results[result["id"]]["rank"] = i + 1
        tournament_seeding[pool_seeding_list[i]] = int(result["id"])

    # Compute and store opponent strength (sum of opponents' points)
    if match.swiss_round is None:
        raise ValueError("Swiss round must be set for opponent strength calculation")
    all_swiss_matches = Match.objects.filter(
        swiss_round=match.swiss_round, status=Match.Status.COMPLETED
    )
    opp_strength: dict[int, int] = {tid: 0 for tid in new_results}
    for m in all_swiss_matches:
        if m.team_1 and m.team_2:
            t1, t2 = m.team_1.id, m.team_2.id
            if t1 in opp_strength:
                opp_stats = new_results.get(t2, {})
                opp_strength[t1] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
            if t2 in opp_strength:
                opp_stats = new_results.get(t1, {})
                opp_strength[t2] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
    for tid in new_results:
        new_results[tid]["opp_strength"] = opp_strength.get(tid, 0)

    return new_results, tournament_seeding


def get_new_bracket_seeding(seeding: dict[int, int], match: Match) -> dict[int, int]:
    if match.team_1 is None or match.team_2 is None:
        return seeding
    if (
        match.placeholder_seed_2 > match.placeholder_seed_1
        and match.score_team_2 > match.score_team_1
    ):
        seeding[match.placeholder_seed_1] = match.team_2.id
        seeding[match.placeholder_seed_2] = match.team_1.id
    elif (
        match.placeholder_seed_1 > match.placeholder_seed_2
        and match.score_team_1 > match.score_team_2
    ):
        seeding[match.placeholder_seed_2] = match.team_1.id
        seeding[match.placeholder_seed_1] = match.team_2.id

    return seeding


@transaction.atomic
def update_match_score_and_results(match: Match, team_1_score: int, team_2_score: int) -> None:
    match.score_team_1 = team_1_score
    match.score_team_2 = team_2_score
    match.status = Match.Status.COMPLETED
    match.save()

    if match.pool is not None:
        update_for_pool_or_position_pool(match, match.pool)

    elif match.cross_pool is not None:
        update_for_bracket_or_cross_pool(match, match.cross_pool)

    elif match.bracket is not None:
        update_for_bracket_or_cross_pool(match, match.bracket)

    elif match.position_pool is not None:
        update_for_pool_or_position_pool(match, match.position_pool)

    elif match.swiss_round is not None:
        update_for_swiss_round(match, match.swiss_round)


@transaction.atomic
def rerun_swiss_round(tournament: Tournament, swiss_round: SwissRound) -> None:
    """Re-rank teams with current tiebreaker logic and re-pair unplayed current round matches.

    Part A: Re-rank using existing W/L/D/GF/GA stats (stats unchanged, only rank order).
    Part B: Optionally re-evaluate bye for the current round (when safe) and
            re-pair SCHEDULED matches using backtracking pairing.
    """

    def _recompute_ranks(
        results: dict[int, dict[str, int]],
        pool_seeding_list: list[int],
    ) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
        """Apply Swiss tiebreakers to assign ranks and update tournament seeding."""
        tournament_seeding_local = {int(k): v for k, v in tournament.current_seeding.items()}
        return recompute_swiss_ranks(
            swiss_round, results, pool_seeding_list, tournament_seeding_local
        )

    def _recompute_opp_strength(results: dict[int, dict[str, int]]) -> None:
        """Recompute opponent strength (sum of opponents' points) for all teams."""
        all_matches = Match.objects.filter(swiss_round=swiss_round, status=Match.Status.COMPLETED)
        opp_strength: dict[int, int] = {tid: 0 for tid in results}
        for m in all_matches:
            if m.team_1 and m.team_2:
                t1, t2 = m.team_1.id, m.team_2.id
                if t1 in opp_strength:
                    opp_stats = results.get(t2, {})
                    opp_strength[t1] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
                if t2 in opp_strength:
                    opp_stats = results.get(t1, {})
                    opp_strength[t2] += opp_stats.get("wins", 0) * 2 + opp_stats.get("draws", 0)
        for tid in results:
            results[tid]["opp_strength"] = opp_strength.get(tid, 0)

    results = {int(k): v for k, v in swiss_round.results.items()}
    pool_seeding_list = sorted(map(int, swiss_round.initial_seeding.keys()))
    current_round = swiss_round.current_round

    teams_by_id = {team.id: team for team in tournament.teams.all()}
    is_odd = len(teams_by_id) % 2 != 0

    # Determine whether it is safe to change the bye for the current round:
    # we only change it if no matches in the current round have been completed.
    current_round_matches = Match.objects.filter(
        swiss_round=swiss_round, sequence_number=current_round
    )
    has_completed_in_current_round = current_round_matches.filter(
        status=Match.Status.COMPLETED
    ).exists()

    byes: dict[str, int] = dict(swiss_round.byes or {})
    existing_bye_str = byes.get(str(current_round))
    existing_bye_id: int | None = int(existing_bye_str) if existing_bye_str is not None else None

    # If we have an odd-team Swiss and the current round has no completed matches,
    # undo this round's existing bye (if any) before re-ranking.
    if is_odd and not has_completed_in_current_round and existing_bye_id is not None:
        stats = results.get(existing_bye_id)
        if stats is not None:
            stats["wins"] = max(0, stats.get("wins", 0) - 1)
            stats["GF"] = max(0, stats.get("GF", 0) - BYE_SCORE)
        byes.pop(str(current_round), None)
        existing_bye_id = None

    # Part A: Re-rank with current Swiss tiebreaker logic (using latest stats).
    results, tournament_seeding = _recompute_ranks(results, pool_seeding_list)

    # If this is an odd-team Swiss and no games are completed in the current round,
    # (re)select the bye team based on the latest rankings and re-apply the bye
    # using the same BYE_SCORE convention.
    if is_odd and not has_completed_in_current_round:
        # Persist intermediate results/byes so they reflect the latest stats
        # before we decide the new bye team.
        swiss_round.results = results
        swiss_round.byes = byes
        swiss_round.save(update_fields=["results", "byes"])

        # Recompute bye based on the latest Swiss standings.
        new_bye_team_id = select_bye_team(swiss_round)

        stats = results.get(new_bye_team_id)
        if stats is not None:
            stats["wins"] = stats.get("wins", 0) + 1
            stats["GF"] = stats.get("GF", 0) + BYE_SCORE
        else:
            results[new_bye_team_id] = {
                "wins": 1,
                "losses": 0,
                "draws": 0,
                "GF": BYE_SCORE,
                "GA": 0,
            }

        byes[str(current_round)] = new_bye_team_id

        # Re-rank again now that the (possibly new) bye has been applied.
        results, tournament_seeding = _recompute_ranks(results, pool_seeding_list)
        bye_team_id_for_pairings: int | None = new_bye_team_id
    else:
        bye_team_id_for_pairings = existing_bye_id

    # Recompute opponent strength from the final results.
    _recompute_opp_strength(results)

    swiss_round.results = results
    swiss_round.byes = byes
    swiss_round.save()
    tournament.current_seeding = tournament_seeding
    tournament.save()

    # Part B: Re-pair SCHEDULED matches in current round
    scheduled_matches = list(
        Match.objects.filter(
            swiss_round=swiss_round,
            sequence_number=current_round,
            status=Match.Status.SCHEDULED,
        ).order_by("id")
    )

    if not scheduled_matches:
        return

    pairings = generate_swiss_pairings(swiss_round, exclude_team_id=bye_team_id_for_pairings)

    # Build rank map from current results
    team_rank: dict[int, int] = swiss_team_rank_map(results)

    for i, (t1_id, t2_id) in enumerate(pairings):
        if i < len(scheduled_matches):
            match = scheduled_matches[i]
            match.team_1 = teams_by_id[t1_id]
            match.team_2 = teams_by_id[t2_id]
            match.placeholder_seed_1 = team_rank[t1_id]
            match.placeholder_seed_2 = team_rank[t2_id]
            match.save()

    if current_round > 1:
        reorder_swiss_round_matches(swiss_round, current_round)


@transaction.atomic
def populate_fixtures(tournament_id: int) -> None:
    pools = Pool.objects.filter(tournament=tournament_id)
    cross_pool = CrossPool.objects.filter(tournament=tournament_id)
    brackets = Bracket.objects.filter(tournament=tournament_id)
    position_pools = PositionPool.objects.filter(tournament=tournament_id)
    tournament = Tournament.objects.get(id=tournament_id)
    teams_by_id = {team.id: team for team in tournament.teams.all()}

    is_all_pool_matches_complete = True

    # Handle Swiss round progression
    swiss_rounds = SwissRound.objects.filter(tournament=tournament_id)
    is_all_swiss_complete = True

    for swiss_round in swiss_rounds:
        if swiss_round.current_round == 0:
            is_all_swiss_complete = False
            continue

        current_round_matches = Match.objects.filter(
            swiss_round=swiss_round, sequence_number=swiss_round.current_round
        )
        is_current_round_complete = all(
            m.status == Match.Status.COMPLETED for m in current_round_matches
        )

        if is_current_round_complete:
            # Snapshot current round results
            round_results = dict(swiss_round.round_results or {})
            round_results[str(swiss_round.current_round)] = {
                k: dict(v) for k, v in swiss_round.results.items()
            }
            swiss_round.round_results = round_results

            if swiss_round.current_round < swiss_round.num_rounds:
                # Generate next round pairings
                next_round = swiss_round.current_round + 1
                assign_swiss_round_teams(tournament, swiss_round, next_round)
                if next_round > 1:
                    reorder_swiss_round_matches(swiss_round, next_round)
                swiss_round.current_round = next_round
                swiss_round.save()
                is_all_swiss_complete = False
            else:
                swiss_round.save()
        else:
            is_all_swiss_complete = False

    if not is_all_swiss_complete:
        is_all_pool_matches_complete = False

    # When Swiss is complete, assign teams to next stage matches (cross pool/bracket/position pool)
    if is_all_swiss_complete and swiss_rounds.exists():
        tournament.refresh_from_db()
        tournament_current_seeding = {int(k): v for k, v in tournament.current_seeding.items()}

        for swiss_round in swiss_rounds:
            swiss_seeding_list = list(map(int, swiss_round.initial_seeding.keys()))

            for seed in swiss_seeding_list:
                team_id = int(tournament_current_seeding[seed])

                next_matches = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(tournament=tournament_id, sequence_number=1)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.filter(cross_pool__isnull=False)
                        .filter(tournament=tournament_id, sequence_number=2)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.filter(
                            Q(bracket__isnull=False) | Q(position_pool__isnull=False)
                        )
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )

                for match in next_matches:
                    if match.placeholder_seed_1 == seed and match.team_1 is None:
                        match.team_1 = teams_by_id[team_id]
                    elif match.placeholder_seed_2 == seed and match.team_2 is None:
                        match.team_2 = teams_by_id[team_id]

                    if (
                        match.status == Match.Status.YET_TO_FIX
                        and match.team_1 is not None
                        and match.team_2 is not None
                    ):
                        match.status = Match.Status.SCHEDULED

                    match.save()

    for pool in pools:
        is_current_pool_matches_completed = True

        matches = Match.objects.filter(pool=pool)
        for match in matches:
            if match.status != Match.Status.COMPLETED:
                is_current_pool_matches_completed = False
                is_all_pool_matches_complete = False

        if is_current_pool_matches_completed:
            tournament_current_seeding = {int(k): v for k, v in tournament.current_seeding.items()}
            pool_initial_seeding_list = list(map(int, pool.initial_seeding.keys()))

            for seed in pool_initial_seeding_list:
                team_id = int(tournament_current_seeding[seed])

                next_matches = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(tournament=tournament_id, sequence_number=1)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.filter(cross_pool__isnull=False)
                        .filter(tournament=tournament_id, sequence_number=2)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.filter(
                            Q(bracket__isnull=False) | Q(position_pool__isnull=False)
                        )
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )

                for match in next_matches:
                    if match.placeholder_seed_1 == seed and match.team_1 is None:
                        match.team_1 = teams_by_id[team_id]
                    elif match.placeholder_seed_2 == seed and match.team_2 is None:
                        match.team_2 = teams_by_id[team_id]

                    if (
                        match.status == Match.Status.YET_TO_FIX
                        and match.team_1 is not None
                        and match.team_2 is not None
                    ):
                        match.status = Match.Status.SCHEDULED

                    match.save()

    if is_all_pool_matches_complete:
        if cross_pool.count() > 0:
            if not cross_pool[0].initial_seeding:
                cp = cross_pool[0]
                cp.initial_seeding = tournament.current_seeding
                cp.current_seeding = tournament.current_seeding
                cp.save()
        else:
            for bracket in brackets:
                if bracket.initial_seeding[next(iter(bracket.initial_seeding.keys()))] == 0:
                    for key in list(bracket.initial_seeding.keys()):
                        bracket.initial_seeding[int(key)] = tournament.current_seeding[key]
                        bracket.current_seeding[int(key)] = tournament.current_seeding[key]
                    bracket.save()

            for position_pool in position_pools:
                if (
                    position_pool.initial_seeding[next(iter(position_pool.initial_seeding.keys()))]
                    == 0
                ):
                    for i, key in enumerate(list(position_pool.initial_seeding.keys())):
                        position_pool.initial_seeding[int(key)] = tournament.current_seeding[key]
                        position_pool.results[tournament.current_seeding[key]] = {
                            "rank": i + 1,
                            "wins": 0,
                            "losses": 0,
                            "draws": 0,
                            "GF": 0,  # Goals For
                            "GA": 0,  # Goals Against
                        }
                    position_pool.save()

    if cross_pool.count() > 0:
        matches = Match.objects.filter(cross_pool=cross_pool[0])
        for match in matches:
            if match.status == Match.Status.COMPLETED:
                _next_cp_seed_1 = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(
                        tournament=tournament_id,
                        sequence_number__gt=match.sequence_number,
                    )
                    .filter(
                        Q(placeholder_seed_1=match.placeholder_seed_1)
                        | Q(placeholder_seed_2=match.placeholder_seed_1)
                    )
                    .order_by("sequence_number")
                )
                _first_cp_seed_1 = _next_cp_seed_1.first()
                if _first_cp_seed_1 is not None:
                    next_matches_seed_1 = _next_cp_seed_1.filter(
                        sequence_number=_first_cp_seed_1.sequence_number
                    )
                else:
                    next_matches_seed_1 = (
                        Match.objects.filter(
                            Q(bracket__isnull=False) | Q(position_pool__isnull=False)
                        )
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(
                            Q(placeholder_seed_1=match.placeholder_seed_1)
                            | Q(placeholder_seed_2=match.placeholder_seed_1)
                        )
                    )

                _next_cp_seed_2 = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(
                        tournament=tournament_id,
                        sequence_number__gt=match.sequence_number,
                    )
                    .filter(
                        Q(placeholder_seed_1=match.placeholder_seed_2)
                        | Q(placeholder_seed_2=match.placeholder_seed_2)
                    )
                    .order_by("sequence_number")
                )
                _first_cp_seed_2 = _next_cp_seed_2.first()
                if _first_cp_seed_2 is not None:
                    next_matches_seed_2 = _next_cp_seed_2.filter(
                        sequence_number=_first_cp_seed_2.sequence_number
                    )
                else:
                    next_matches_seed_2 = (
                        Match.objects.filter(
                            Q(bracket__isnull=False) | Q(position_pool__isnull=False)
                        )
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(
                            Q(placeholder_seed_1=match.placeholder_seed_2)
                            | Q(placeholder_seed_2=match.placeholder_seed_2)
                        )
                    )

                for next_match in next_matches_seed_1:
                    if (
                        next_match.placeholder_seed_1 == match.placeholder_seed_1
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_1
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]

                    if (
                        next_match.status == Match.Status.YET_TO_FIX
                        and next_match.team_1 is not None
                        and next_match.team_2 is not None
                    ):
                        next_match.status = Match.Status.SCHEDULED

                    next_match.save()

                for next_match in next_matches_seed_2:
                    if (
                        next_match.placeholder_seed_1 == match.placeholder_seed_2
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_2
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]

                    if (
                        next_match.status == Match.Status.YET_TO_FIX
                        and next_match.team_1 is not None
                        and next_match.team_2 is not None
                    ):
                        next_match.status = Match.Status.SCHEDULED

                    next_match.save()

        for bracket in brackets:
            is_this_bracket_seeds_pool_matches_complete = True
            is_this_bracket_seeds_cross_pool_matches_complete = True

            bracket_initial_seeding_list = list(map(int, bracket.initial_seeding.keys()))

            for seed in bracket_initial_seeding_list:
                pool_matches_not_completed = (
                    Match.objects.filter(Q(pool__isnull=False) | Q(swiss_round__isnull=False))
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if pool_matches_not_completed.count() > 0:
                    is_this_bracket_seeds_pool_matches_complete = False

                cross_pool_matches_not_completed = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if cross_pool_matches_not_completed.count() > 0:
                    is_this_bracket_seeds_cross_pool_matches_complete = False

            if (
                is_this_bracket_seeds_pool_matches_complete
                and is_this_bracket_seeds_cross_pool_matches_complete
            ):
                if bracket.initial_seeding[next(iter(bracket.initial_seeding.keys()))] == 0:
                    for key in list(bracket.initial_seeding.keys()):
                        bracket.initial_seeding[int(key)] = tournament.current_seeding[key]
                        bracket.current_seeding[int(key)] = tournament.current_seeding[key]
                    bracket.save()

                next_matches = Match.objects.filter(
                    bracket=bracket, status=Match.Status.YET_TO_FIX, sequence_number=1
                )
                for next_match in next_matches:
                    if next_match.team_1 is None:
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    if next_match.team_2 is None:
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]
                    next_match.status = Match.Status.SCHEDULED
                    next_match.save()

        for position_pool in position_pools:
            is_this_position_pool_seeds_pool_matches_complete = True
            is_this_position_pool_seeds_cross_pool_matches_complete = True

            position_pool_initial_seeding_list = list(
                map(int, position_pool.initial_seeding.keys())
            )

            for seed in position_pool_initial_seeding_list:
                pool_matches_not_completed = (
                    Match.objects.filter(Q(pool__isnull=False) | Q(swiss_round__isnull=False))
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if pool_matches_not_completed.count() > 0:
                    is_this_position_pool_seeds_pool_matches_complete = False

                cross_pool_matches_not_completed = (
                    Match.objects.filter(cross_pool__isnull=False)
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if cross_pool_matches_not_completed.count() > 0:
                    is_this_position_pool_seeds_cross_pool_matches_complete = False

            if (
                is_this_position_pool_seeds_pool_matches_complete
                and is_this_position_pool_seeds_cross_pool_matches_complete
            ):
                if (
                    position_pool.initial_seeding[next(iter(position_pool.initial_seeding.keys()))]
                    == 0
                ):
                    for i, key in enumerate(list(position_pool.initial_seeding.keys())):
                        position_pool.initial_seeding[int(key)] = tournament.current_seeding[key]
                        position_pool.results[tournament.current_seeding[key]] = {
                            "rank": i + 1,
                            "wins": 0,
                            "losses": 0,
                            "draws": 0,
                            "GF": 0,  # Goals For
                            "GA": 0,  # Goals Against
                        }
                    position_pool.save()

                next_matches = Match.objects.filter(
                    position_pool=position_pool, status=Match.Status.YET_TO_FIX
                )
                for next_match in next_matches:
                    if next_match.team_1 is None:
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    if next_match.team_2 is None:
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]
                    next_match.status = Match.Status.SCHEDULED
                    next_match.save()

    for bracket in brackets:
        matches = Match.objects.filter(bracket=bracket)

        for match in matches:
            if match.status == Match.Status.COMPLETED:
                next_matches = Match.objects.filter(
                    sequence_number=match.sequence_number + 1, bracket=bracket
                ).filter(
                    Q(placeholder_seed_1=match.placeholder_seed_1)
                    | Q(placeholder_seed_2=match.placeholder_seed_1)
                    | Q(placeholder_seed_1=match.placeholder_seed_2)
                    | Q(placeholder_seed_2=match.placeholder_seed_2)
                )

                for next_match in next_matches:
                    if (
                        next_match.placeholder_seed_1 == match.placeholder_seed_1
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_1
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]
                    elif (
                        next_match.placeholder_seed_1 == match.placeholder_seed_2
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        ]
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_2
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = teams_by_id[
                            tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        ]

                    if (
                        next_match.status == Match.Status.YET_TO_FIX
                        and next_match.team_1 is not None
                        and next_match.team_2 is not None
                    ):
                        next_match.status = Match.Status.SCHEDULED

                    next_match.save()

    if (
        Match.objects.filter(tournament=tournament_id)
        .exclude(status=Match.Status.COMPLETED)
        .count()
        == 0
    ):
        tournament.status = Tournament.Status.COMPLETED
        tournament.save()


def update_tournament_spirit_rankings(tournament: Tournament) -> None:
    spirit_ranking: list[dict[str, int | float]] = []
    for team in tournament.teams.all():
        team_matches = Match.objects.filter(tournament=tournament).filter(
            Q(team_1=team) | Q(team_2=team)
        )
        points = 0.0
        self_points = 0.0
        matches_count = 0

        for match in team_matches:
            if match.team_1 is None or match.team_2 is None:
                continue

            if (
                match.team_1.id == team.id
                and match.spirit_score_team_1
                and match.self_spirit_score_team_1
            ):
                points += float(match.spirit_score_team_1.total)
                self_points += float(match.self_spirit_score_team_1.total)

                matches_count += 1
            elif (
                match.team_2.id == team.id
                and match.spirit_score_team_2
                and match.self_spirit_score_team_2
            ):
                points += float(match.spirit_score_team_2.total)
                self_points += float(match.self_spirit_score_team_2.total)

                matches_count += 1

        spirit_ranking.append(
            {
                "team_id": team.id,
                "points": round(points / matches_count, ndigits=1) if matches_count > 0 else points,
                "self_points": round(self_points / matches_count, ndigits=1)
                if matches_count > 0
                else self_points,
            }
        )

    tournament.spirit_ranking = rank_spirit_scores(spirit_ranking)
    tournament.save()


def can_manage_tournament(user: User, tournament: Tournament) -> bool:
    """Staff may manage any tournament; directors only the ones they are assigned to."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return tournament.directors.filter(pk=user.pk).exists()


def can_access_tournament_agent(user: User) -> bool:
    """Catalog and agent entry: staff, or anyone assigned as a director somewhere."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    return Tournament.objects.filter(directors=user).exists()


def user_tournament_teams(tournament: Tournament, user: User) -> tuple[int | None, set[int]]:
    player_team_id = 0
    admin_team_ids: set[int] = set()

    try:
        player = user.player_profile
    except Player.DoesNotExist:
        return player_team_id, admin_team_ids

    if tournament.use_uc_registrations:
        if player.ultimate_central_id is None:
            return player_team_id, admin_team_ids

        registrations = UCRegistration.objects.filter(
            event=tournament.event, person_id=player.ultimate_central_id
        )

        for reg in registrations:
            is_player = PLAYER_ROLE in reg.roles
            is_admin = any(role in reg.roles for role in ROLES_ELIGIBLE_TO_SUBMIT_SCORES)

            if is_player:
                player_team_id = reg.team.id

            if is_admin:
                admin_team_ids.add(reg.team.id)

        return player_team_id, admin_team_ids

    else:
        registrations = Registration.objects.filter(event=tournament.event, player=player)

        for reg in registrations:
            if reg.is_playing:
                player_team_id = reg.team.id

            reg_role_name = Registration.Role._value2member_map_[reg.role].label.lower()  # type: ignore[attr-defined]
            is_admin = reg_role_name in ROLES_ELIGIBLE_TO_SUBMIT_SCORES
            if is_admin:
                admin_team_ids.add(reg.team.id)

        return player_team_id, admin_team_ids


def is_submitted_scores_equal(match: Match) -> bool:
    if match.suggested_score_team_1 is None or match.suggested_score_team_2 is None:
        return False

    if (
        match.suggested_score_team_1.score_team_1 == match.suggested_score_team_2.score_team_1
        and match.suggested_score_team_1.score_team_2 == match.suggested_score_team_2.score_team_2
    ):
        return True

    return False


def create_spirit_scores(spirit_score: SpiritScoreUpdateSchema, use_uc_reg: bool) -> SpiritScore:
    score = SpiritScore(
        rules=spirit_score.rules,
        fouls=spirit_score.fouls,
        fair=spirit_score.fair,
        positive=spirit_score.positive,
        communication=spirit_score.communication,
        total=(
            spirit_score.rules
            + spirit_score.fouls
            + spirit_score.fair
            + spirit_score.positive
            + spirit_score.communication
        ),
        comments=spirit_score.comments if spirit_score.comments else None,
    )

    if spirit_score.mvp_id:
        if use_uc_reg:
            mvp = UCPerson.objects.get(id=spirit_score.mvp_id)
            score.mvp = mvp
            with contextlib.suppress(Player.DoesNotExist):
                score.mvp_v2 = Player.objects.get(ultimate_central_id=spirit_score.mvp_id)
        else:
            mvp_v2 = Player.objects.get(id=spirit_score.mvp_id)
            score.mvp_v2 = mvp_v2

    if spirit_score.msp_id:
        if use_uc_reg:
            msp = UCPerson.objects.get(id=spirit_score.msp_id)
            score.msp = msp
            with contextlib.suppress(Player.DoesNotExist):
                score.msp_v2 = Player.objects.get(ultimate_central_id=spirit_score.msp_id)
        else:
            msp_v2 = Player.objects.get(id=spirit_score.msp_id)
            score.msp_v2 = msp_v2

    score.save()
    return score


def get_default_rules() -> str:
    module_dir = os.path.dirname(__file__)
    file_path = os.path.join(module_dir, os.pardir, "templates", "rules_default.md")

    with open(file_path) as data_file:
        data = data_file.read()

    return data


# Helper Functions #####################


def calculate_head_to_head_stats(
    result1: dict[str, int], result2: dict[str, int], tournament_id: int
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    matches = Match.objects.filter(
        Q(
            team_1=result1["id"],
            team_2=result2["id"],
            tournament=tournament_id,
            status=Match.Status.COMPLETED,
        )
        | Q(
            team_2=result1["id"],
            team_1=result2["id"],
            tournament=tournament_id,
            status=Match.Status.COMPLETED,
        )
    )

    wins = {result1["id"]: 0, result2["id"]: 0}
    goal_diff = {result1["id"]: 0, result2["id"]: 0}  # Goal Diff
    goal_for = {result1["id"]: 0, result2["id"]: 0}  # Goals For

    for match in matches:
        if match.team_1 is None or match.team_2 is None:
            continue

        if match.team_1.id == result1["id"]:
            if match.score_team_1 > match.score_team_2:
                wins[result1["id"]] += 1
            elif match.score_team_2 > match.score_team_1:
                wins[result2["id"]] += 1

            goal_diff[result1["id"]] += match.score_team_1 - match.score_team_2
            goal_diff[result2["id"]] += match.score_team_2 - match.score_team_1

            goal_for[result1["id"]] += match.score_team_1
            goal_for[result2["id"]] += match.score_team_2
        else:
            if match.score_team_2 > match.score_team_1:
                wins[result1["id"]] += 1
            elif match.score_team_1 > match.score_team_2:
                wins[result2["id"]] += 1

            goal_diff[result1["id"]] += match.score_team_2 - match.score_team_1
            goal_diff[result2["id"]] += match.score_team_1 - match.score_team_2

            goal_for[result1["id"]] += match.score_team_2
            goal_for[result2["id"]] += match.score_team_1

    return wins, goal_diff, goal_for


def create_bracket_sequence_matches(
    tournament: Tournament, bracket: Bracket, start: int, end: int, seq_num: int
) -> None:
    for i in range(0, ((end - start) + 1) // 2):
        seed_1 = start + i
        seed_2 = end - i

        match = Match(
            name=get_bracket_match_name(start, end, seed_1, seed_2),
            tournament=tournament,
            bracket=bracket,
            sequence_number=seq_num,
            placeholder_seed_1=seed_1,
            placeholder_seed_2=seed_2,
        )

        match.save()

    if end - start > 1:
        create_bracket_sequence_matches(
            tournament, bracket, start, start + (((end - start) + 1) // 2) - 1, seq_num + 1
        )
        create_bracket_sequence_matches(
            tournament, bracket, start + (((end - start) + 1) // 2), end, seq_num + 1
        )


def rank_spirit_scores(scores: list[dict[str, int | float]]) -> list[dict[str, int | float]]:
    spirit_points = sorted({r["points"] for r in scores}, reverse=True)

    # Assign the ranks to teams based on points - use the same rank for teams
    # with same number of points.
    for score in scores:
        score["rank"] = spirit_points.index(score["points"]) + 1

    return sorted(scores, key=lambda x: x["rank"])


def update_for_pool_or_position_pool(match: Match, pool: Pool | PositionPool) -> None:
    results = pool.results
    results = {int(k): v for k, v in results.items()}

    pool_seeding_list = list(map(int, pool.initial_seeding.keys()))
    pool_seeding_list.sort()
    tournament_seeding = match.tournament.current_seeding

    new_results, new_tournament_seeding = get_new_pool_results(
        results, match, pool_seeding_list, tournament_seeding
    )

    pool.results = new_results
    pool.save()

    match.tournament.current_seeding = new_tournament_seeding
    match.tournament.save()


def update_for_swiss_round(match: Match, swiss_round: SwissRound) -> None:
    results = swiss_round.results
    results = {int(k): v for k, v in results.items()}

    pool_seeding_list = list(map(int, swiss_round.initial_seeding.keys()))
    pool_seeding_list.sort()
    tournament_seeding = match.tournament.current_seeding

    new_results, new_tournament_seeding = get_new_swiss_results(
        results, match, pool_seeding_list, tournament_seeding
    )

    swiss_round.results = new_results
    swiss_round.save()

    match.tournament.current_seeding = new_tournament_seeding
    match.tournament.save()


def update_for_bracket_or_cross_pool(
    match: Match, bracket_or_cross_pool: Bracket | CrossPool
) -> None:
    seeding = bracket_or_cross_pool.current_seeding
    bracket_or_cross_pool.current_seeding = get_new_bracket_seeding(seeding, match)
    bracket_or_cross_pool.save()

    tournament_seeding = match.tournament.current_seeding
    match.tournament.current_seeding = get_new_bracket_seeding(tournament_seeding, match)
    match.tournament.save()


def validate_seeds_and_teams(
    tournament: Tournament, seeding: dict[int, int]
) -> tuple[bool, validation_error_dict]:
    incoming_seeds = seeding.keys()
    incoming_teams = seeding.values()

    tournament_team_ids = tournament.teams.all().values_list("id", flat=True)

    seeds = range(1, len(tournament_team_ids) + 1)

    valid_seeds_and_teams = True
    errors = {}

    # incoming seeding list should be equal to range(len(roster_size))
    missing_seeds = set(seeds) - set(incoming_seeds)
    if missing_seeds:
        valid_seeds_and_teams = False
        errors["missing_seeds"] = list(missing_seeds)

    # Seeds must be an integer between 1 and {roster_size}
    wrong_seeds = set(incoming_seeds) - set(seeds)
    if wrong_seeds:
        valid_seeds_and_teams = False
        errors["wrong_seeds"] = list(wrong_seeds)

    # incoming teams list should be same as rostered teams list
    missing_teams = set(tournament_team_ids) - set(incoming_teams)
    if missing_teams:
        errors["missing_teams"] = list(missing_teams)
        valid_seeds_and_teams = False

    # all teams in the update should belong to the roster
    wrong_teams = set(incoming_teams) - set(tournament_team_ids)
    if wrong_teams:
        valid_seeds_and_teams = False
        errors["wrong_teams"] = list(wrong_teams)

    # same team cannot be in 2 different seeds
    duplicate_teams: list[int] = [
        team for team, occurence in Counter(incoming_teams).items() if occurence > 1
    ]
    if duplicate_teams:
        valid_seeds_and_teams = False
        errors["duplicate_teams"] = duplicate_teams

    return valid_seeds_and_teams, errors


def validate_new_pool(
    tournament: Tournament, new_pool: set[int]
) -> tuple[bool, validation_error_dict]:
    # same seed shouldn't be added in multiple pools
    other_pools_in_tournament = Pool.objects.filter(tournament=tournament).values_list(
        "initial_seeding", flat=True
    )
    already_present_seeds: set[int] = set()
    for pool in other_pools_in_tournament:
        already_present_seeds.update(
            map(int, pool.keys())
        )  # Pool.initial_seeding : dict[seed(str), team_id(int)]. Convert seeds from str to ints

    # Also check seeds used in Swiss rounds
    swiss_rounds = SwissRound.objects.filter(tournament=tournament).values_list(
        "initial_seeding", flat=True
    )
    for swiss_seeding in swiss_rounds:
        already_present_seeds.update(map(int, swiss_seeding.keys()))

    repeated_seeds_in_new_pool = already_present_seeds.intersection(new_pool)
    # the seed shouldn't negative, 0 or more than roster size

    num_teams_in_tournament = tournament.teams.all().values_list("id", flat=True).count()

    invalid_seeds = list(filter(lambda seed: not 1 <= seed <= num_teams_in_tournament, new_pool))
    valid_pool = True
    errors = {}

    if repeated_seeds_in_new_pool:
        errors["repeated_seeds_in_new_pool"] = list(repeated_seeds_in_new_pool)
        valid_pool = False
    if invalid_seeds:
        errors["invalid_seeds"] = invalid_seeds
        valid_pool = False

    return valid_pool, errors


def validate_bracket_name(name: str) -> tuple[bool, message_response | None]:
    """Bracket names must be seed ranges like '1-8' spanning an even seed count.

    Odd-sized ranges would silently create no matches (create_bracket_matches
    only handles even sizes), and non-numeric names crash seed parsing.
    """
    expected_parts = 2
    parts = name.split("-")
    if len(parts) != expected_parts or not all(part.isdigit() for part in parts):
        return False, {"message": "Bracket name must be a seed range like '1-8' or '9-16'"}

    start, end = int(parts[0]), int(parts[1])
    if start < 1 or end <= start:
        return False, {
            "message": f"Bracket name '{name}' is not a valid seed range: "
            "the first seed must be 1 or higher and lower than the last seed"
        }

    if ((end - start) + 1) % 2 != 0:
        return False, {
            "message": f"Bracket '{name}' spans an odd number of seeds "
            f"({(end - start) + 1}); brackets need an even seed count. "
            "Use a position pool for the leftover seeds instead."
        }

    return True, None


def get_bracket_match_name(start: int, end: int, seed_1: int, seed_2: int) -> str:
    """Get type of bracket match (Quarter Finals, Semi Finals, Finals, Position match)"""

    position_match_bracket_size = 2
    semifinal_bracket_size = 4
    quarterfinal_bracket_size = 8

    bracket_size = (end - start) + 1
    seed = min(seed_1, seed_2)

    if bracket_size == position_match_bracket_size:
        if seed == 1:
            return "Finals"
        return f"{seed}{ordinal_suffix(seed)} Place"

    if bracket_size == semifinal_bracket_size:
        if 1 <= seed <= bracket_size:
            return "Semi Finals"
        else:
            return f"{start}-{end} Bracket"

    if bracket_size == quarterfinal_bracket_size:
        if 1 <= seed <= bracket_size:
            return "Quarter Finals"
        else:
            return f"{start}-{end} Bracket"

    return ""


def can_register_player_to_series_event(
    event: Event, team: Team, player: Player
) -> tuple[bool, message_response | None]:
    if not event.series:
        return True, None

    if not SeriesRegistration.objects.filter(
        series=event.series, team=team, player=player
    ).exists():
        return False, {
            "message": "Player is not part of series roster",
            "description": "Players need to be added to the series roster first, to be added to the tournament roster.",
            "action_name": "Series roster",
            "action_href": f"/series/{event.series.slug}/team/{team.slug}",
        }

    num_total_registered = Registration.objects.filter(event=event, team=team).count()

    if not (num_total_registered + 1) <= event.series.event_max_players_total:
        return False, {
            "message": f"You can only roster {event.series.event_max_players_total} total players"
        }

    match player.match_up:
        case player.MatchupTypes.MALE:
            num_male_matching_registered = Registration.objects.filter(
                event=event, team=team, player__match_up=player.MatchupTypes.MALE
            ).count()

            if not (num_male_matching_registered + 1) <= event.series.event_max_players_male:
                return False, {
                    "message": f"You can only roster {event.series.event_max_players_male} male players"
                }

        case player.MatchupTypes.FEMALE:
            num_female_matching_registered = Registration.objects.filter(
                event=event, team=team, player__match_up=player.MatchupTypes.FEMALE
            ).count()

            if not (num_female_matching_registered + 1) <= event.series.event_max_players_female:
                return False, {
                    "message": f"You can only roster {event.series.event_max_players_female} female players"
                }

    return True, None
