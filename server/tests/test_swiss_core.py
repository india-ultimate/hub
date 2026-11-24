import random
from unittest import TestCase

from server.swiss.pairing import draw_order, pair_teams, select_bye
from server.swiss.ranking import draw_lots, opponent_strength, points, rank_teams


def row(wins: int = 0, draws: int = 0, gf: int = 0, ga: int = 0) -> dict[str, int]:
    return {"wins": wins, "losses": 0, "draws": draws, "GF": gf, "GA": ga}


class TestSwissCore(TestCase):
    def test_points_draw_is_one_bye_is_win(self) -> None:
        self.assertEqual(points({"wins": 1, "draws": 1}), 3)
        self.assertEqual(points({"wins": 1}), 2)

    def test_h2h_beats_opponent_strength(self) -> None:
        results = {1: row(1), 2: row(1), 8: row(5), 9: row(0)}
        games = [(1, 2, 1, 0), (2, 8, 0, 1)]
        self.assertEqual(opponent_strength(results, games), {1: 2, 2: 12, 8: 2, 9: 0})
        self.assertEqual(rank_teams(results, games, {}), [8, 1, 2, 9])

    def test_opponent_strength_splits_tie(self) -> None:
        results = {1: row(1), 2: row(1), 8: row(2), 9: row(0)}
        games = [(1, 8, 0, 1), (2, 9, 1, 0)]
        self.assertEqual(opponent_strength(results, games), {1: 4, 2: 0, 8: 2, 9: 2})
        self.assertEqual(rank_teams(results, games, {}), [8, 1, 2, 9])

    def test_goal_difference_splits_tie_before_goals_scored(self) -> None:
        results = {1: row(1, gf=20, ga=18), 2: row(1, gf=10, ga=3)}
        self.assertEqual(rank_teams(results, [], {}), [2, 1])

    def test_goals_scored_splits_tie_on_equal_difference(self) -> None:
        results = {1: row(1, gf=10, ga=5), 2: row(1, gf=12, ga=7)}
        self.assertEqual(rank_teams(results, [], {}), [2, 1])

    def test_gf_is_last_stat(self) -> None:
        results = {1: row(1, gf=10, ga=5), 2: row(1, gf=12, ga=7)}
        self.assertEqual(rank_teams(results, [], {1: 1, 2: 2}), [2, 1])

    def test_lot_breaks_full_tie(self) -> None:
        results = {1: row(1, gf=5, ga=5), 2: row(1, gf=5, ga=5)}
        self.assertEqual(rank_teams(results, [], {1: 2, 2: 1}), [2, 1])

    def test_lot_lower_first(self) -> None:
        results = {1: row(), 2: row(), 3: row()}
        self.assertEqual(rank_teams(results, [], {1: 3, 2: 1, 3: 2}), [2, 3, 1])

    def test_no_lots_falls_back_to_team_id(self) -> None:
        results = {5: row(), 3: row(), 4: row()}
        self.assertEqual(rank_teams(results, [], {}), [3, 4, 5])

    def test_restart_rule_three_way(self) -> None:
        results = {1: row(2), 2: row(2, gf=10), 3: row(2, gf=30), 7: row(3)}
        games = [(1, 2, 1, 0), (2, 3, 1, 0), (3, 1, 1, 0), (1, 7, 1, 0)]
        self.assertEqual(rank_teams(results, games, {}), [7, 1, 2, 3])

    def test_drawn_game_gives_no_h2h_win(self) -> None:
        results = {1: row(draws=1, gf=5, ga=5), 2: row(draws=1, gf=9, ga=5)}
        self.assertEqual(rank_teams(results, [(1, 2, 3, 3)], {}), [2, 1])

    def test_rank_independent_of_input_order(self) -> None:
        results = {i: row(1 + i % 2, gf=i, ga=1) for i in range(1, 9)}
        games = [(1, 2, 1, 0), (3, 4, 2, 2), (5, 6, 3, 1), (7, 8, 0, 4), (2, 3, 1, 0)]
        lots = draw_lots(results)
        expected = rank_teams(results, games, lots)
        for seed in range(20):
            rng = random.Random(seed)  # noqa: S311
            items = list(results.items())
            rng.shuffle(items)
            shuffled = games[:]
            rng.shuffle(shuffled)
            self.assertEqual(rank_teams(dict(items), shuffled, lots), expected)

    def test_pair_adjacent(self) -> None:
        self.assertEqual(pair_teams([1, 2, 3, 4, 5, 6], set()), [(1, 2), (3, 4), (5, 6)])

    def test_pair_backtracks(self) -> None:
        played = {frozenset((1, 3)), frozenset((3, 4))}
        self.assertEqual(pair_teams([1, 2, 3, 4], played), [(1, 4), (2, 3)])

    def test_pair_falls_back_to_rematch(self) -> None:
        played = {frozenset((a, b)) for a in range(1, 5) for b in range(a + 1, 5)}
        pairs = pair_teams([1, 2, 3, 4], played)
        self.assertEqual(pairs, [(1, 2), (3, 4)])

    def test_select_bye_lowest_without_bye(self) -> None:
        self.assertEqual(select_bye([1, 2, 3, 4], {4}), 3)

    def test_select_bye_everyone_had_one(self) -> None:
        self.assertEqual(select_bye([1, 2, 3], {1, 2, 3}), 3)

    def test_draw_lots_distinct_1_to_n(self) -> None:
        lots = draw_lots([10, 20, 30, 40])
        self.assertEqual(sorted(lots.values()), [1, 2, 3, 4])
        self.assertEqual(set(lots), {10, 20, 30, 40})

    def test_draw_order_is_permutation(self) -> None:
        self.assertEqual(sorted(draw_order([4, 2, 9, 1])), [1, 2, 4, 9])
