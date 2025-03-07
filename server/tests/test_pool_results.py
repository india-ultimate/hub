from server.tests.base import ApiBaseTestCase
from server.tournament.models import Match, Pool
from server.tournament.utils import get_new_pool_results


class TestGetNewPoolResults(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        # Create teams
        self.team_a = self.teams[0]
        self.team_b = self.teams[1]
        self.team_c = self.teams[2]
        self.team_d = self.teams[3]

        pool_results = {
            self.team_a.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_b.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_c.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_d.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
        }

        # Create pool
        self.pool = Pool.objects.create(
            name="Pool 1",
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding={
                1: self.team_a.id,
                2: self.team_b.id,
                3: self.team_c.id,
                4: self.team_d.id,
            },
            results=pool_results,
        )

    def tearDown(self) -> None:
        # Delete all matches from the tournament
        Match.objects.filter(tournament=self.tournament).delete()
        super().tearDown()

    def test_clear_winner(self) -> None:
        """Test scenario where one team wins all matches"""
        # Initial empty results
        old_results = {
            self.team_a.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_b.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_c.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
        }

        # Create all matches
        # A vs B - A wins
        match1 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_b,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )

        # Process first match
        old_results, tournament_seeding = get_new_pool_results(
            old_results, match1, [1, 2, 3], {1: 0, 2: 0, 3: 0}
        )

        # B vs C - B wins
        match2 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_b,
            team_2=self.team_c,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=2,
            placeholder_seed_2=3,
        )

        # Process second match
        old_results, tournament_seeding = get_new_pool_results(
            old_results, match2, [1, 2, 3], tournament_seeding
        )

        # A vs C - A wins (final match)
        match3 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_c,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=3,
        )

        # Process final match
        new_results, new_seeding = get_new_pool_results(
            old_results, match3, [1, 2, 3], tournament_seeding
        )

        # Team A should be first with 2 wins
        self.assertEqual(new_results[self.team_a.id]["rank"], 1)
        self.assertEqual(new_results[self.team_a.id]["wins"], 2)

        # Team B should be second with 1 win
        self.assertEqual(new_results[self.team_b.id]["rank"], 2)
        self.assertEqual(new_results[self.team_b.id]["wins"], 1)

        # Team C should be last with 0 wins
        self.assertEqual(new_results[self.team_c.id]["rank"], 3)
        self.assertEqual(new_results[self.team_c.id]["wins"], 0)

    def test_circular_tie(self) -> None:
        """Test scenario with circular tie between 3 teams"""
        # Initial empty results
        old_results = {
            self.team_a.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_b.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_c.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_d.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
        }

        # Create all matches
        # A vs B - A wins 15-5
        match1 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_b,
            score_team_1=15,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match1, [1, 2, 3, 4], {1: 0, 2: 0, 3: 0, 4: 0}
        )

        # A vs C - A wins 10-5
        match2 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_c,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=3,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match2, [1, 2, 3, 4], tournament_seeding
        )

        # A vs D - A wins 5-0
        match3 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_d,
            score_team_1=5,
            score_team_2=0,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=4,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match3, [1, 2, 3, 4], tournament_seeding
        )

        # B vs C - B wins 15-5
        match4 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_b,
            team_2=self.team_c,
            score_team_1=15,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=2,
            placeholder_seed_2=3,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match4, [1, 2, 3, 4], tournament_seeding
        )

        # C vs D - C wins 10-5
        match5 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_c,
            team_2=self.team_d,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=3,
            placeholder_seed_2=4,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match5, [1, 2, 3, 4], tournament_seeding
        )

        # B vs D - D wins 5-0 (creates circular tie)
        match6 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_b,
            team_2=self.team_d,
            score_team_1=0,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=2,
            placeholder_seed_2=4,
        )

        new_results, new_seeding = get_new_pool_results(
            old_results, match6, [1, 2, 3, 4], tournament_seeding
        )

        # Team A should be first (3 wins)
        self.assertEqual(new_results[self.team_a.id]["rank"], 1)
        self.assertEqual(new_results[self.team_a.id]["wins"], 3)

        # Verify teams are ranked by goal difference
        self.assertEqual(new_results[self.team_b.id]["rank"], 2)  # Best GD (+5)
        self.assertEqual(new_results[self.team_d.id]["rank"], 3)  # Second best GD (+0)
        self.assertEqual(new_results[self.team_c.id]["rank"], 4)  # Worst GD (-5)

    def test_circular_tie_2(self) -> None:
        """Test scenario where three teams have same number of wins"""
        # Initial empty results
        old_results = {
            self.team_a.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_b.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
            self.team_c.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0},
        }

        # A vs C - A wins 10-5
        match1 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_a,
            team_2=self.team_c,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=3,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match1, [1, 2, 3], {1: 0, 2: 0, 3: 0}
        )

        # B vs A - B wins 15-5
        match2 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_b,
            team_2=self.team_a,
            score_team_1=15,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=2,
            placeholder_seed_2=1,
        )

        old_results, tournament_seeding = get_new_pool_results(
            old_results, match2, [1, 2, 3], tournament_seeding
        )

        # C vs B - C wins 10-5
        match3 = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            team_1=self.team_c,
            team_2=self.team_b,
            score_team_1=10,
            score_team_2=5,
            sequence_number=1,
            placeholder_seed_1=3,
            placeholder_seed_2=2,
        )

        new_results, new_seeding = get_new_pool_results(
            old_results, match3, [1, 2, 3], tournament_seeding
        )

        # All teams have 1 win, but B has most goal difference
        self.assertEqual(new_results[self.team_a.id]["wins"], 1)
        self.assertEqual(new_results[self.team_b.id]["wins"], 1)
        self.assertEqual(new_results[self.team_c.id]["wins"], 1)

        # Team B should be first (most Goals Difference - 5)
        self.assertEqual(new_results[self.team_b.id]["rank"], 1)

        # Team C second (second most Goals Difference - 0)
        self.assertEqual(new_results[self.team_c.id]["rank"], 2)

        # Team A third (third most Goals Difference - -5)
        self.assertEqual(new_results[self.team_a.id]["rank"], 3)
