from server.tests.base import ApiBaseTestCase, create_pool, start_tournament
from server.tournament.models import Bracket, CrossPool, Match, Pool


class TestTournamentLifecycle(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Create Pool A (Seeds 1,4,5,8)
        self.pool_a = self.create_pool("A", [1, 4, 5, 8])

        # Create Pool B (Seeds 2,3,6,7)
        self.pool_b = self.create_pool("B", [2, 3, 6, 7])

        # Create top four bracket with placeholder seeds
        self.top_four_bracket = self.create_bracket(
            "1-4",
            {
                "1": 0,  # Pool A 1st
                "2": 0,  # Pool B 2nd
                "3": 0,  # Pool B 1st
                "4": 0,  # Pool A 2nd
            },
        )

        start_tournament(self.tournament)

    def test_full_tournament_lifecycle(self) -> None:
        """
        Test full tournament lifecycle:
        1. Play pool games and verify standings
        2. Verify bracket population
        3. Play bracket games
        4. Verify final standings
        """
        # Step 1: Submit pool game scores
        # Pool A matches
        pool_a_matches = Match.objects.filter(pool=self.pool_a).order_by("id")
        pool_a_scores = [
            (15, 10),  # 1st vs 4th
            (15, 8),  # 1st vs 5th
            (15, 7),  # 1st vs 8th
            (13, 15),  # 4th vs 5th
            (15, 10),  # 4th vs 8th
            (15, 12),  # 5th vs 8th
        ]

        for match, score in zip(pool_a_matches, pool_a_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Pool B matches
        pool_b_matches = Match.objects.filter(pool=self.pool_b).order_by("id")
        pool_b_scores = [
            (15, 13),  # 2nd vs 3rd
            (15, 10),  # 2nd vs 6th
            (15, 8),  # 2nd vs 7th
            (15, 12),  # 3rd vs 6th
            (15, 11),  # 3rd vs 7th
            (13, 15),  # 6th vs 7th
        ]

        for match, score in zip(pool_b_matches, pool_b_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Verify pool standings
        response = self.client.get(f"/api/tournament/pools?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)
        pools = response.json()

        pool_a_data = next(p for p in pools if p["name"] == "A")
        pool_b_data = next(p for p in pools if p["name"] == "B")

        # Verify final pool standings
        self.assertEqual(pool_a_data["results"][str(self.teams[0].id)]["rank"], 1)  # Seed 1 first
        self.assertEqual(pool_a_data["results"][str(self.teams[4].id)]["rank"], 2)  # Seed 5 second
        self.assertEqual(pool_a_data["results"][str(self.teams[3].id)]["rank"], 3)  # Seed 4 third
        self.assertEqual(pool_a_data["results"][str(self.teams[7].id)]["rank"], 4)  # Seed 8 fourth

        self.assertEqual(pool_b_data["results"][str(self.teams[1].id)]["rank"], 1)  # Seed 2 first
        self.assertEqual(pool_b_data["results"][str(self.teams[2].id)]["rank"], 2)  # Seed 3 second
        self.assertEqual(pool_b_data["results"][str(self.teams[6].id)]["rank"], 3)  # Seed 7 third
        self.assertEqual(pool_b_data["results"][str(self.teams[5].id)]["rank"], 4)  # Seed 6 fourth

        # Step 2: Verify bracket population
        self.top_four_bracket.refresh_from_db()
        bracket_matches = Match.objects.filter(bracket=self.top_four_bracket).order_by("id")

        # Verify teams are correctly placed in bracket
        for match in bracket_matches[:2]:  # Only check first two matches (semifinals)
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            if match.team_1 and match.team_2:  # Type guard for mypy
                if match.placeholder_seed_1 == 1:
                    self.assertEqual(match.team_1.id, self.teams[0].id)  # Pool A 1st (1)
                    self.assertEqual(match.team_2.id, self.teams[4].id)  # Pool A 2nd (4)
                else:
                    self.assertEqual(match.team_1.id, self.teams[1].id)  # Pool B 1st (2)
                    self.assertEqual(match.team_2.id, self.teams[2].id)  # Pool B 2nd (3)

        # Step 3: Play bracket games
        # Submit semifinal scores
        semifinal_scores = [
            (15, 12),  # Semi 1 (1 vs 4)
            (15, 13),  # Semi 2 (2 vs 3)
        ]

        for match, score in zip(bracket_matches[:2], semifinal_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Verify finals and 3rd place matches are generated correctly
        finals_matches = bracket_matches[2:]
        self.assertEqual(len(finals_matches), 2)

        finals = finals_matches[0]
        third_place = finals_matches[1]

        self.assertEqual(finals.name, "Finals")
        self.assertEqual(third_place.name, "3rd Place")

        # Verify teams are assigned
        self.assertIsNotNone(finals.team_1)
        self.assertIsNotNone(finals.team_2)
        self.assertIsNotNone(third_place.team_1)
        self.assertIsNotNone(third_place.team_2)

        # Finals should have winners of semis (teams 1 and 2)
        if finals.team_1 and finals.team_2 and third_place.team_1 and third_place.team_2:
            self.assertEqual(finals.team_1.id, self.teams[0].id)  # Winner of semi 1
            self.assertEqual(finals.team_2.id, self.teams[1].id)  # Winner of semi 2

            # 3rd place should have losers of semis (teams 4 and 3)
            self.assertEqual(third_place.team_1.id, self.teams[2].id)  # Loser of semi 2
            self.assertEqual(third_place.team_2.id, self.teams[4].id)  # Loser of semi 1

        # Submit finals and 3rd place scores
        finals_scores = [
            (15, 10),  # Finals (1 v 2)
            (11, 15),  # 3rd Place (3 v 4)
        ]

        for match, score in zip(finals_matches, finals_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Step 4: Verify final tournament standings
        response = self.client.get(f"/api/tournament?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)
        standings = response.json()["current_seeding"]
        print(standings)

        # Verify top 4 standings
        self.assertEqual(standings["1"], self.teams[0].id)  # 1st seed wins
        self.assertEqual(standings["2"], self.teams[1].id)  # 2nd seed second
        self.assertEqual(standings["3"], self.teams[4].id)  # 3rd seed third
        self.assertEqual(standings["4"], self.teams[2].id)  # 4th seed fourth

    def tearDown(self) -> None:
        # Clean up all matches
        Match.objects.filter(tournament=self.tournament).delete()
        # Clean up pools and brackets
        Pool.objects.filter(tournament=self.tournament).delete()
        Bracket.objects.filter(tournament=self.tournament).delete()
        super().tearDown()

    def create_pool(self, name: str, seeds: list[int]) -> Pool:
        """Helper method to create a pool with initial seeding"""
        pool_seeding = {}
        pool_results = {}

        for seed in seeds:
            team_id = self.tournament.initial_seeding[str(seed)]
            pool_seeding[seed] = team_id
            pool_results[team_id] = {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "GF": 0,
                "GA": 0,
            }

        pool = Pool.objects.create(
            name=name,
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding=pool_seeding,
            results=pool_results,
        )

        # Create pool matches
        for i, seed_1 in enumerate(seeds):
            for seed_2 in seeds[i + 1 :]:
                Match.objects.create(
                    tournament=self.tournament,
                    pool=pool,
                    sequence_number=1,
                    placeholder_seed_1=seed_1,
                    placeholder_seed_2=seed_2,
                )

        return pool

    def create_bracket(self, name: str, seeding: dict[str, int]) -> Bracket:
        """Helper method to create a bracket with initial seeding and matches"""
        bracket = Bracket.objects.create(
            name=name,
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding=seeding,
            current_seeding=seeding.copy(),
        )

        # Create bracket matches
        # Semi-finals: 1v4, 2v3
        Match.objects.create(
            tournament=self.tournament,
            bracket=bracket,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=4,
        )
        Match.objects.create(
            tournament=self.tournament,
            bracket=bracket,
            sequence_number=1,
            placeholder_seed_1=2,
            placeholder_seed_2=3,
        )
        # Finals: Winner of 1v4 vs Winner of 2v3
        Match.objects.create(
            tournament=self.tournament,
            bracket=bracket,
            sequence_number=2,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            name="Finals",
        )

        # 3rd Place: Loser of 1v4 vs Loser of 2v3
        Match.objects.create(
            tournament=self.tournament,
            bracket=bracket,
            sequence_number=2,
            placeholder_seed_1=3,
            placeholder_seed_2=4,
            name="3rd Place",
        )

        return bracket


class TestCrossPoolSeqGapProgression(ApiBaseTestCase):
    """
    Regression test: a seed that plays CP seq 1 and seq 3 (no seq 2 match)
    should have its team populated in the seq 3 match after seq 1 completes.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Two 2-team pools so pool matches are trivial (one match each)
        self.pool_a = create_pool("A", self.tournament, [1, 2])
        self.pool_b = create_pool("B", self.tournament, [3, 4])

        # Create the CrossPool container
        response = self.client.post(
            f"/api/tournament/cross-pool/{self.tournament.id}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.cross_pool = CrossPool.objects.get(tournament=self.tournament)

        # CP seq 1: seed 1 vs seed 3
        Match.objects.create(
            tournament=self.tournament,
            cross_pool=self.cross_pool,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=3,
        )
        # CP seq 2: seed 2 vs seed 4 — seed 1 has NO match here (the gap)
        Match.objects.create(
            tournament=self.tournament,
            cross_pool=self.cross_pool,
            sequence_number=2,
            placeholder_seed_1=2,
            placeholder_seed_2=4,
        )
        # CP seq 3: seed 1 vs seed 2 — seed 1 jumps from seq 1 to seq 3
        self.cp_seq3 = Match.objects.create(
            tournament=self.tournament,
            cross_pool=self.cross_pool,
            sequence_number=3,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )

        start_tournament(self.tournament)

    def _score_match(self, match: Match, score_1: int, score_2: int) -> None:
        response = self.client.post(
            f"/api/match/{match.id}/score",
            {"team_1_score": score_1, "team_2_score": score_2},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_cp_seq3_populated_after_seq1_completes(self) -> None:
        """
        Completing pool matches triggers CP seq 1 population.
        Completing CP seq 1 should populate CP seq 3 for seed 1,
        skipping seq 2 where seed 1 has no match.
        """
        # Resolve the team that corresponds to seed 1 before any matches
        seed_1_team_id = self.tournament.initial_seeding["1"]

        # Complete both pool matches (higher seed wins each)
        pool_a_match = Match.objects.get(pool=self.pool_a)
        pool_b_match = Match.objects.get(pool=self.pool_b)
        self._score_match(pool_a_match, 15, 10)
        self._score_match(pool_b_match, 15, 10)

        # CP seq 1 should now have teams assigned
        cp_seq1 = Match.objects.get(cross_pool=self.cross_pool, sequence_number=1)
        self.assertIsNotNone(cp_seq1.team_1, "CP seq 1 should have team_1 after pools complete")
        self.assertIsNotNone(cp_seq1.team_2, "CP seq 1 should have team_2 after pools complete")
        if cp_seq1.team_1:  # Type guard for mypy
            self.assertEqual(cp_seq1.team_1.id, seed_1_team_id)

        # Complete CP seq 1 (seed 1 wins)
        self._score_match(cp_seq1, 15, 10)

        # CP seq 3 must now have seed 1's team populated,
        # even though seed 1 has no CP seq 2 match
        self.cp_seq3.refresh_from_db()
        self.assertIsNotNone(
            self.cp_seq3.team_1,
            "CP seq 3 team_1 should be populated after seq 1 completes despite gap at seq 2",
        )
        if self.cp_seq3.team_1:  # Type guard for mypy
            self.assertEqual(
                self.cp_seq3.team_1.id,
                seed_1_team_id,
                "CP seq 3 team_1 should be seed 1's team",
            )

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        Pool.objects.filter(tournament=self.tournament).delete()
        CrossPool.objects.filter(tournament=self.tournament).delete()
        super().tearDown()
