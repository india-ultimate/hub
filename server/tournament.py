# mypy: ignore-errors
#
# ruff: noqa
#
# FIXME: Remove this after writing good/type safe code

from functools import cmp_to_key

from django.db.models import Q

from server.models import Bracket, CrossPool, Match, Pool, PositionPool, Team, Tournament


def compare_pool_results(
    result1: dict[str, int], result2: dict[str, int], tournament_id: int
) -> int:
    if result1["wins"] != result2["wins"]:
        return result2["wins"] - result1["wins"]

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
    GD = {result1["id"]: 0, result2["id"]: 0}  # Goal Diff
    GF = {result1["id"]: 0, result2["id"]: 0}  # Goals For

    for match in matches:
        if match.team_1.id == result1["id"]:
            if match.score_team_1 > match.score_team_2:
                wins[result1["id"]] += 1
            elif match.score_team_2 > match.score_team_1:
                wins[result2["id"]] += 1

            GD[result1["id"]] += match.score_team_1 - match.score_team_2
            GD[result2["id"]] += match.score_team_2 - match.score_team_1

            GF[result1["id"]] += match.score_team_1
            GF[result2["id"]] += match.score_team_2
        else:
            if match.score_team_2 > match.score_team_1:
                wins[result1["id"]] += 1
            elif match.score_team_1 > match.score_team_2:
                wins[result2["id"]] += 1

            GD[result1["id"]] += match.score_team_2 - match.score_team_1
            GD[result2["id"]] += match.score_team_1 - match.score_team_2

            GF[result1["id"]] += match.score_team_2
            GF[result2["id"]] += match.score_team_1

    if wins[result1["id"]] != wins[result2["id"]]:
        return wins[result2["id"]] - wins[result1["id"]]

    if GD[result1["id"]] != GD[result2["id"]]:
        return GD[result2["id"]] - GD[result1["id"]]

    overall_GD_1 = result1["GF"] - result1["GA"]
    overall_GD_2 = result2["GF"] - result2["GA"]

    if overall_GD_1 != overall_GD_2:
        return overall_GD_2 - overall_GD_1

    if GF[result1["id"]] != GF[result2["id"]]:
        return GF[result2["id"]] - GF[result1["id"]]

    return result2["GF"] - result1["GF"]


def get_new_pool_results(
    old_results: dict[int, dict[str, int]],
    match: Match,
    pool_seeding_list: list[int],
    tournament_seeding: dict[int, int],
) -> tuple[dict[int, dict[str, int]], dict]:
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

    results_list = []
    for team_id, result in old_results.items():
        result["id"] = team_id
        results_list.append(result)

    ranked_results = sorted(
        results_list,
        key=cmp_to_key(
            lambda result1, result2: compare_pool_results(result1, result2, match.tournament.id)
        ),
    )

    new_results = {}

    for i, result in enumerate(ranked_results):
        new_results[result["id"]] = result
        new_results[result["id"]]["rank"] = i + 1

        tournament_seeding[pool_seeding_list[i]] = int(result["id"])

    return new_results, tournament_seeding


def get_new_bracket_seeding(seeding: dict[int, int], match: Match) -> dict:
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


def populate_fixtures(tournament_id: int) -> None:
    pools = Pool.objects.filter(tournament=tournament_id)
    cross_pool = CrossPool.objects.filter(tournament=tournament_id)
    brackets = Bracket.objects.filter(tournament=tournament_id)
    position_pools = PositionPool.objects.filter(tournament=tournament_id)
    tournament = Tournament.objects.get(id=tournament_id)

    is_all_pool_matches_complete = True

    for pool in pools:
        is_current_pool_matches_completed = True

        matches = Match.objects.filter(pool=pool)
        for match in matches:
            if match.status != Match.Status.COMPLETED:
                is_current_pool_matches_completed = False
                is_all_pool_matches_complete = False

        if is_current_pool_matches_completed:
            tournament_current_seeding = {
                int(k): v for k, v in pool.tournament.current_seeding.items()
            }
            pool_initial_seeding_list = list(map(int, pool.initial_seeding.keys()))

            for seed in pool_initial_seeding_list:
                team_id = int(tournament_current_seeding[seed])

                if cross_pool.count() > 0:
                    next_matches = (
                        Match.objects.exclude(cross_pool__isnull=True)
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )
                else:
                    next_matches = (
                        Match.objects.exclude(bracket__isnull=True)
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                    )

                for match in next_matches:
                    if match.placeholder_seed_1 == seed and match.team_1 is None:
                        match.team_1 = Team.objects.get(id=team_id)
                    elif match.placeholder_seed_2 == seed and match.team_2 is None:
                        match.team_2 = Team.objects.get(id=team_id)

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
        is_all_cross_pool_matches_complete = True
        matches = Match.objects.filter(cross_pool=cross_pool[0])
        for match in matches:
            if match.status == Match.Status.COMPLETED:
                next_matches = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id, sequence_number=match.sequence_number + 1)
                    .filter(
                        Q(placeholder_seed_1=match.placeholder_seed_1)
                        | Q(placeholder_seed_2=match.placeholder_seed_1)
                        | Q(placeholder_seed_1=match.placeholder_seed_2)
                        | Q(placeholder_seed_2=match.placeholder_seed_2)
                    )
                )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.filter(
                            Q(bracket__isnull=False) | Q(position_pool__isnull=False)
                        )
                        .filter(tournament=tournament_id, sequence_number=1)
                        .filter(
                            Q(placeholder_seed_1=match.placeholder_seed_1)
                            | Q(placeholder_seed_2=match.placeholder_seed_1)
                            | Q(placeholder_seed_1=match.placeholder_seed_2)
                            | Q(placeholder_seed_2=match.placeholder_seed_2)
                        )
                    )

                for next_match in next_matches:
                    print(next_match.id)
                    if (
                        next_match.placeholder_seed_1 == match.placeholder_seed_1
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_1
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )
                    elif (
                        next_match.placeholder_seed_1 == match.placeholder_seed_2
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_2
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )

                    if (
                        next_match.status == Match.Status.YET_TO_FIX
                        and next_match.team_1 is not None
                        and next_match.team_2 is not None
                    ):
                        next_match.status = Match.Status.SCHEDULED

                    next_match.save()

            else:
                is_all_cross_pool_matches_complete = False

        if is_all_cross_pool_matches_complete:
            for bracket in brackets:
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
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    if next_match.team_2 is None:
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )
                    next_match.status = Match.Status.SCHEDULED
                    next_match.save()

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

                next_matches = Match.objects.filter(
                    position_pool=position_pool, status=Match.Status.YET_TO_FIX
                )
                for next_match in next_matches:
                    if next_match.team_1 is None:
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    if next_match.team_2 is None:
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )
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
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_1
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )
                    elif (
                        next_match.placeholder_seed_1 == match.placeholder_seed_2
                        and next_match.team_1 is None
                    ):
                        next_match.team_1 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_1)]
                        )
                    elif (
                        next_match.placeholder_seed_2 == match.placeholder_seed_2
                        and next_match.team_2 is None
                    ):
                        next_match.team_2 = Team.objects.get(
                            id=tournament.current_seeding[str(next_match.placeholder_seed_2)]
                        )

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