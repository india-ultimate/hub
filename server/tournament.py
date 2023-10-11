from functools import cmp_to_key, partial

from django.db.models import Q

from server.models import Bracket, CrossPool, Match, Pool, PositionPool, Team, Tournament

# Exported Functions ####################


def create_pool_matches(tournament: Tournament, pool: Pool) -> None:
    pool_seeding_list = list(map(int, pool.initial_seeding.keys()))

    for i, x in enumerate(pool_seeding_list):
        for _j, y in enumerate(pool_seeding_list[i + 1 :], i + 1):
            match = Match(
                tournament=tournament,
                pool=pool,
                sequence_number=1,
                placeholder_seed_1=x,
                placeholder_seed_2=y,
            )

            match.save()


def create_bracket_matches(tournament: Tournament, bracket: Bracket) -> None:
    start, end = map(int, bracket.name.split("-"))
    if ((end - start) + 1) % 2 == 0:
        create_bracket_sequence_matches(tournament, bracket, start, end, 1)


def create_position_pool_matches(tournament: Tournament, position_pool: PositionPool) -> None:
    position_pool_seeding_list = list(map(int, position_pool.initial_seeding.keys()))

    for i, x in enumerate(position_pool_seeding_list):
        for _j, y in enumerate(position_pool_seeding_list[i + 1 :], i + 1):
            match = Match(
                tournament=tournament,
                position_pool=position_pool,
                sequence_number=1,
                placeholder_seed_1=x,
                placeholder_seed_2=y,
            )

            match.save()


def compare_pool_results(
    result1: dict[str, int], result2: dict[str, int], tournament_id: int
) -> int:
    """
    This is the comparator function for comparing pool results
    The order of precedence is as follows:
    1. Games won in pool
    2. Games won counting only games between tied teams
    3. Goal Difference only games between tied teams
    4. Goal Difference counting all pool games
    5. Goals Scored only games between tied teams
    6. Goals Scored counting all pool games
    """

    # Rule 1
    if result1["wins"] != result2["wins"]:
        return result2["wins"] - result1["wins"]

    # Calculate Head-to-Head Data
    wins, goal_diff, goal_for = calculate_head_to_head_stats(result1, result2, tournament_id)

    # Rule 2
    if wins[result1["id"]] != wins[result2["id"]]:
        return wins[result2["id"]] - wins[result1["id"]]

    # Rule 3
    if goal_diff[result1["id"]] != goal_diff[result2["id"]]:
        return goal_diff[result2["id"]] - goal_diff[result1["id"]]

    overall_gd_1 = result1["GF"] - result1["GA"]
    overall_gd_2 = result2["GF"] - result2["GA"]

    # Rule 4
    if overall_gd_1 != overall_gd_2:
        return overall_gd_2 - overall_gd_1

    # Rule 5
    if goal_for[result1["id"]] != goal_for[result2["id"]]:
        return goal_for[result2["id"]] - goal_for[result1["id"]]

    # Rule 6
    return result2["GF"] - result1["GF"]


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

    results_list = []
    for team_id, result in old_results.items():
        result["id"] = team_id
        results_list.append(result)

    ranked_results = sorted(
        results_list,
        key=cmp_to_key(partial(compare_pool_results, tournament_id=match.tournament.id)),
    )

    new_results = {}

    for i, result in enumerate(ranked_results):
        new_results[result["id"]] = result
        new_results[result["id"]]["rank"] = i + 1

        tournament_seeding[pool_seeding_list[i]] = int(result["id"])

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

                next_matches = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id, sequence_number=1)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if next_matches.count() == 0:
                    next_matches = (
                        Match.objects.exclude(cross_pool__isnull=True)
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
        matches = Match.objects.filter(cross_pool=cross_pool[0])
        for match in matches:
            if match.status == Match.Status.COMPLETED:
                next_matches_seed_1 = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id, sequence_number=match.sequence_number + 1)
                    .filter(
                        Q(placeholder_seed_1=match.placeholder_seed_1)
                        | Q(placeholder_seed_2=match.placeholder_seed_1)
                    )
                )

                if next_matches_seed_1.count() == 0:
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

                next_matches_seed_2 = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id, sequence_number=match.sequence_number + 1)
                    .filter(
                        Q(placeholder_seed_1=match.placeholder_seed_2)
                        | Q(placeholder_seed_2=match.placeholder_seed_2)
                    )
                )

                if next_matches_seed_2.count() == 0:
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

                    if (
                        next_match.status == Match.Status.YET_TO_FIX
                        and next_match.team_1 is not None
                        and next_match.team_2 is not None
                    ):
                        next_match.status = Match.Status.SCHEDULED

                    next_match.save()

                for next_match in next_matches_seed_2:
                    print(next_match.id)
                    if (
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

        for bracket in brackets:
            is_this_bracket_seeds_cross_pool_matches_complete = True

            bracket_initial_seeding_list = list(map(int, bracket.initial_seeding.keys()))

            for seed in bracket_initial_seeding_list:
                cross_pool_matches_not_completed = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if cross_pool_matches_not_completed.count() > 0:
                    is_this_bracket_seeds_cross_pool_matches_complete = False

            if is_this_bracket_seeds_cross_pool_matches_complete:
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
            is_this_position_pool_seeds_cross_pool_matches_complete = True

            position_pool_initial_seeding_list = list(
                map(int, position_pool.initial_seeding.keys())
            )

            for seed in position_pool_initial_seeding_list:
                cross_pool_matches_not_completed = (
                    Match.objects.exclude(cross_pool__isnull=True)
                    .filter(tournament=tournament_id)
                    .exclude(status=Match.Status.COMPLETED)
                    .filter(Q(placeholder_seed_1=seed) | Q(placeholder_seed_2=seed))
                )

                if cross_pool_matches_not_completed.count() > 0:
                    is_this_position_pool_seeds_cross_pool_matches_complete = False

            if is_this_position_pool_seeds_cross_pool_matches_complete:
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


def update_tournament_spirit_rankings(tournament: Tournament) -> None:
    spirit_ranking = []
    for team in tournament.teams.all():
        team_matches = Match.objects.filter(tournament=tournament).filter(
            Q(team_1=team) | Q(team_2=team)
        )
        points = 0.0
        matches_count = 0

        for match in team_matches:
            if match.team_1 is None or match.team_2 is None:
                continue

            if match.team_1.id == team.id and match.spirit_score_team_1:
                spirit_score = match.spirit_score_team_1
                points += (
                    float(spirit_score.rules)
                    + float(spirit_score.fouls)
                    + float(spirit_score.fair)
                    + float(spirit_score.positive)
                    + float(spirit_score.communication)
                )
                matches_count += 1
            elif match.team_2.id == team.id and match.spirit_score_team_2:
                spirit_score = match.spirit_score_team_2
                points += (
                    float(spirit_score.rules)
                    + float(spirit_score.fouls)
                    + float(spirit_score.fair)
                    + float(spirit_score.positive)
                    + float(spirit_score.communication)
                )
                matches_count += 1

        spirit_ranking.append(
            {
                "team_id": team.id,
                "points": round(points / matches_count, ndigits=1) if matches_count > 0 else points,
            }
        )

    spirit_ranking.sort(key=lambda x: x["points"], reverse=True)

    tournament.spirit_ranking = spirit_ranking
    tournament.save()


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
        match = Match(
            tournament=tournament,
            bracket=bracket,
            sequence_number=seq_num,
            placeholder_seed_1=start + i,
            placeholder_seed_2=end - i,
        )

        match.save()

    if end - start > 1:
        create_bracket_sequence_matches(
            tournament, bracket, start, start + (((end - start) + 1) // 2) - 1, seq_num + 1
        )
        create_bracket_sequence_matches(
            tournament, bracket, start + (((end - start) + 1) // 2), end, seq_num + 1
        )
