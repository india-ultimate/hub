from django.test import SimpleTestCase

from server.tournament.utils import rank_spirit_scores

# current_seeding, {position: team_id}: Karnataka 1st, Bengal 2nd, Kerala 3rd.
FINAL_STANDINGS = {"1": 1, "2": 3, "3": 2}


class RankSpiritScoresTest(SimpleTestCase):
    def test_ranks_on_the_true_average_not_the_displayed_one(self) -> None:
        scores = [
            {"team_id": 1, "points": 83 / 8, "self_points": 10.0},  # Karnataka 10.375
            {"team_id": 2, "points": 73 / 7, "self_points": 10.0},  # Kerala    10.4286
            {"team_id": 3, "points": 83.2 / 8, "self_points": 10.0},  # Bengal  10.4
        ]

        ranked = rank_spirit_scores(scores, FINAL_STANDINGS)

        self.assertEqual([2, 3, 1], [s["team_id"] for s in ranked])
        self.assertEqual([1, 2, 3], [s["rank"] for s in ranked])
        self.assertEqual([10.43, 10.4, 10.38], [s["points"] for s in ranked])

    def test_level_teams_are_separated_by_final_placement(self) -> None:
        scores = [
            {"team_id": 2, "points": 10.4, "self_points": 9.0},
            {"team_id": 3, "points": 10.4, "self_points": 9.0},
            {"team_id": 1, "points": 10.4, "self_points": 9.0},
        ]

        ranked = rank_spirit_scores(scores, FINAL_STANDINGS)

        self.assertEqual([1, 3, 2], [s["team_id"] for s in ranked])
        self.assertEqual([1, 2, 3], [s["rank"] for s in ranked])

    def test_float_noise_does_not_pose_as_a_tie_break(self) -> None:
        # Ten matches of 10.4 average to 10.400000000000002.
        accumulated = 0.0
        for _ in range(10):
            accumulated += 10.4
        scores = [
            {"team_id": 2, "points": accumulated / 10, "self_points": 9.0},
            {"team_id": 1, "points": 10.4, "self_points": 9.0},
        ]

        ranked = rank_spirit_scores(scores, FINAL_STANDINGS)

        self.assertEqual([1, 2], [s["team_id"] for s in ranked])

    def test_unplaced_teams_sort_behind_placed_ones(self) -> None:
        scores = [
            {"team_id": 99, "points": 10.4, "self_points": 9.0},
            {"team_id": 1, "points": 10.4, "self_points": 9.0},
        ]

        ranked = rank_spirit_scores(scores, FINAL_STANDINGS)

        self.assertEqual([1, 99], [s["team_id"] for s in ranked])

    def test_works_without_standings_or_self_points(self) -> None:
        # Migration 0039 calls this with one argument.
        ranked = rank_spirit_scores(
            [{"team_id": 9, "points": 11.0}, {"team_id": 8, "points": 12.0}]
        )

        self.assertEqual([8, 9], [s["team_id"] for s in ranked])
        self.assertEqual([1, 2], [s["rank"] for s in ranked])
