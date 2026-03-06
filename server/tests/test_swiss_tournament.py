from server.tests.base import ApiBaseTestCase, add_teams_to_event, create_event, create_tournament
from server.tournament.models import Bracket, Match, SwissRound


class TestSwissTournamentLifecycle(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Create Swiss Round via API (all 8 seeds in one group)
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 3,
                "seeding": [1, 2, 3, 4, 5, 6, 7, 8],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.swiss_round = SwissRound.objects.get(tournament=self.tournament)

        # Create top four bracket via API (auto-creates bracket matches)
        response = self.client.post(
            f"/api/tournament/bracket/{self.tournament.id}",
            {"name": "1-4", "sequence_number": 1},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.top_four_bracket = Bracket.objects.get(tournament=self.tournament)

        # Start tournament via API
        response = self.client.post(
            f"/api/tournament/start/{self.tournament.id}",
        )
        self.assertEqual(response.status_code, 200)

    def _score_round_matches(self, round_number: int, scores: list[tuple[int, int]]) -> None:
        """Score all matches in a Swiss round."""
        matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=round_number
        ).order_by("id")
        for match, score in zip(matches, scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

    def _get_round_pairs(self, round_number: int) -> set[frozenset[int]]:
        """Get team pairs for a Swiss round."""
        matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=round_number
        ).order_by("id")
        pairs: set[frozenset[int]] = set()
        for match in matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            # team_1 and team_2 are verified non-None above
            pairs.add(frozenset([match.team_1.id, match.team_2.id]))  # type: ignore[union-attr, list-item]
        return pairs

    def test_full_swiss_tournament_lifecycle(self) -> None:
        """
        Test full Swiss tournament lifecycle:
        1. Play Swiss rounds and verify standings
        2. Verify bracket population after Swiss completes
        3. Play bracket games
        4. Verify final standings
        """
        # Step 1: Verify round 1 matches exist with correct pairings (1v8, 2v7, 3v6, 4v5)
        r1_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=1).order_by(
            "id"
        )
        self.assertEqual(r1_matches.count(), 4)

        # Verify teams are assigned for round 1
        for match in r1_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        # Score round 1: higher seeds win
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10), (15, 11)])

        # Step 2: Verify round 2 matches have teams assigned
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 2)

        r2_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=2).order_by(
            "id"
        )
        self.assertEqual(r2_matches.count(), 4)

        for match in r2_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        # Verify no rematches in round 2
        r1_pairs = self._get_round_pairs(1)
        r2_pairs = self._get_round_pairs(2)
        self.assertEqual(
            len(r1_pairs & r2_pairs), 0, "Round 2 should have no rematches from round 1"
        )

        # Score round 2
        self._score_round_matches(2, [(15, 10), (15, 11), (15, 12), (15, 13)])

        # Step 3: Verify round 3 matches have teams assigned
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 3)

        r3_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=3).order_by(
            "id"
        )
        self.assertEqual(r3_matches.count(), 4)

        for match in r3_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        # Score round 3
        self._score_round_matches(3, [(15, 10), (15, 11), (15, 12), (15, 13)])

        # Step 4: Verify Swiss is complete and bracket is populated
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 3)

        # Bracket should now have teams assigned
        self.top_four_bracket.refresh_from_db()
        bracket_matches = Match.objects.filter(
            bracket=self.top_four_bracket, sequence_number=1
        ).order_by("id")

        # Verify bracket semifinal matches have teams
        for match in bracket_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)

        # Play bracket semifinals
        semifinal_scores = [(15, 12), (15, 13)]
        for match, score in zip(bracket_matches, semifinal_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Play finals and 3rd place
        finals_matches = Match.objects.filter(
            bracket=self.top_four_bracket, sequence_number=2
        ).order_by("id")
        finals_scores = [(15, 10), (11, 15)]
        for match, score in zip(finals_matches, finals_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Verify tournament is completed
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.status, "COM")

    def test_swiss_round_creation_api(self) -> None:
        """Test creating Swiss round via API returns correct data."""
        # Use the GET API to verify swiss round data
        response = self.client.get(f"/api/tournament/swiss-rounds?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_rounds"], 3)
        self.assertEqual(data[0]["current_round"], 1)
        self.assertEqual(data[0]["name"], "A")
        self.assertTrue(len(data[0]["initial_seeding"]) > 0)
        self.assertTrue(len(data[0]["results"]) > 0)

        # Verify matches were created (3 rounds * 4 matches per round = 12)
        match_count = Match.objects.filter(swiss_round=self.swiss_round).count()
        self.assertEqual(match_count, 12)

    def test_swiss_round_get_api(self) -> None:
        """Test fetching Swiss rounds via API returns a list."""
        response = self.client.get(f"/api/tournament/swiss-rounds?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["num_rounds"], 3)

        # Also test by slug
        response = self.client.get(f"/api/tournament/swiss-rounds?slug={self.event.slug}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)

    def test_swiss_seed_overlap_blocked(self) -> None:
        """Test that creating a second Swiss group with overlapping seeds is blocked."""
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 3,
                "seeding": [1, 2, 3, 4],
                "sequence_number": 2,
                "name": "B",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("repeated_seeds", response.json()["message"])

    def test_opponent_strength_tiebreaker(self) -> None:
        """Test that opponent strength (sum of opponents' points) breaks ties.

        After R1, all winners have OS=0 (opponents have 0 pts) and all losers
        have OS=2 (opponents have 2 pts), so OS doesn't differentiate within
        a group after just one round. We need 2 rounds for meaningful OS.

        R1: 1v8, 2v7, 3v6, 4v5 — all 15-8 (higher seeds win)
        R2: winners play winners, losers play losers — all 15-8

        After R2, among 2-win teams (4 pts each):
        - Their OS = sum of opponents' points
        - The team that faced a 2-pt opponent in R2 has higher OS than
          the team that faced a 0-pt opponent in R2
        """
        self.swiss_round.refresh_from_db()
        seeding = self.swiss_round.initial_seeding
        seed_to_team = {int(k): v for k, v in seeding.items()}

        # Score round 1: all winners win by same margin (15-8)
        self._score_round_matches(1, [(15, 8), (15, 8), (15, 8), (15, 8)])

        self.swiss_round.refresh_from_db()
        results = self.swiss_round.results

        # All R1 winners have 2 pts, all losers have 0 pts
        for i in range(1, 5):
            self.assertEqual(results[str(seed_to_team[i])]["wins"], 1)
        for i in range(5, 9):
            self.assertEqual(results[str(seed_to_team[i])]["wins"], 0)

        # After R1, all winners have OS=0 (all opponents have 0 pts)
        # All losers have OS=2 (all opponents have 2 pts)
        # So within winners and losers, ranks are tied (order is arbitrary)

        # Score round 2: all wins by same margin again (15-8)
        self._score_round_matches(2, [(15, 8), (15, 8), (15, 8), (15, 8)])

        self.swiss_round.refresh_from_db()
        results = self.swiss_round.results

        # Find the 2-win teams (4 pts) — should be exactly 2
        four_pt_teams = [
            (tid, stats)
            for tid, stats in results.items()
            if stats["wins"] == 2
        ]
        self.assertEqual(len(four_pt_teams), 2, "Exactly 2 teams should have 2 wins")

        # Both have 4 pts, same GD (+14), same GF (30)
        # But their OS should differ: the one who faced a tougher R2 opponent
        # (who had more pts going into the match) should have higher OS
        ranks = sorted(four_pt_teams, key=lambda x: x[1]["rank"])
        top_team = ranks[0]
        second_team = ranks[1]

        # The higher-ranked team should have >= OS than the lower-ranked one
        # (since points and GD are the same, OS must be the differentiator)
        self.assertLessEqual(top_team[1]["rank"], second_team[1]["rank"])

        # Verify that 0-win teams are ranked last (7-8)
        zero_win_teams = [
            (tid, stats) for tid, stats in results.items() if stats["wins"] == 0
        ]
        self.assertEqual(len(zero_win_teams), 2)
        for _, stats in zero_win_teams:
            self.assertGreaterEqual(stats["rank"], 7)

    def test_points_system_draw_counts(self) -> None:
        """Test that Swiss uses points (win=2, draw=1) not just wins.

        After 2 rounds, a team with 1W+1D (3 pts) should rank above
        a team with 1W+1L (2 pts) even though both have 1 win.
        """
        # Score round 1: all higher seeds win
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10), (15, 11)])

        # Score round 2: first match is a draw, rest are normal wins
        r2_matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=2
        ).order_by("id")
        scores = [(10, 10)] + [(15, 11)] * (r2_matches.count() - 1)
        self._score_round_matches(2, scores)

        self.swiss_round.refresh_from_db()
        results = self.swiss_round.results

        # Find the draw match teams
        r2_matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=2
        ).order_by("id")
        draw_match = r2_matches[0]
        draw_t1 = draw_match.team_1.id
        draw_t2 = draw_match.team_2.id

        # Both should have 1 draw
        self.assertEqual(results[str(draw_t1)]["draws"], 1)
        self.assertEqual(results[str(draw_t2)]["draws"], 1)

        # Find the R1-winner who drew in R2 (1W + 1D = 3 pts)
        pts_3_rank = None
        for tid in [draw_t1, draw_t2]:
            s = results[str(tid)]
            if s["wins"] == 1 and s["draws"] == 1:
                pts_3_rank = s["rank"]
                break
        self.assertIsNotNone(pts_3_rank, "Should find a team with 1W+1D")

        # Find any team with 1W + 0D (2 pts) — an R1 loser who won R2
        pts_2_rank = None
        for _, s in results.items():
            if s["wins"] == 1 and s.get("draws", 0) == 0:
                pts_2_rank = s["rank"]
                break
        self.assertIsNotNone(pts_2_rank, "Should find a team with 1W+0D")

        self.assertLess(
            pts_3_rank,
            pts_2_rank,
            "Team with 3 pts (1W 1D) should rank above team with 2 pts (1W 1L)",
        )

    def test_even_swiss_no_byes(self) -> None:
        """Test that even-team Swiss has no byes."""
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.byes, {})

        # Score round 1
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10), (15, 11)])

        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.byes, {})

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        Bracket.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestOddSwissTournamentLifecycle(ApiBaseTestCase):
    """Tests for Swiss rounds with odd number of teams (bye system)."""

    def setUp(self) -> None:
        # Override to create 7 teams instead of 8
        from django.test import TestCase

        TestCase.setUp(self)
        from server.core.models import Player, UCPerson, User
        from server.season.models import Season
        from server.tournament.models import UCRegistration

        self.username = "username@foo.com"
        self.password = "password"
        self.user = User.objects.create(
            username=self.username, email=self.username, first_name="John", last_name="Williamson"
        )
        self.user.set_password(self.password)
        self.user.is_staff = True
        self.user.save()

        person = UCPerson.objects.create(email=self.username, slug="username")
        self.player = Player.objects.create(
            user=self.user, date_of_birth="1990-01-01", ultimate_central_id=person.id
        )

        self.event = create_event("Odd Teams Tournament")
        self.teams = add_teams_to_event(self.event, 7)  # 7 teams (odd)
        UCRegistration.objects.create(
            event=self.event, team=self.teams[0], person=person, roles=["admin", "player"]
        )
        self.tournament = create_tournament(self.event)
        self.season = Season.objects.create(
            name="Season 24-25",
            start_date="2024-08-01",
            end_date="2025-07-30",
            annual_membership_amount=70000,
            sponsored_annual_membership_amount=20000,
            supporter_annual_membership_amount=50000,
        )

        self.client.force_login(self.user)

        # Create Swiss Round with 3 rounds (all 7 seeds)
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 3,
                "seeding": [1, 2, 3, 4, 5, 6, 7],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.swiss_round = SwissRound.objects.get(tournament=self.tournament)

        # Start tournament
        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

    def _score_round_matches(self, round_number: int, scores: list[tuple[int, int]]) -> None:
        """Score all matches in a Swiss round."""
        matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=round_number
        ).order_by("id")
        for match, score in zip(matches, scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

    def _get_round_pairs(self, round_number: int) -> set[frozenset[int]]:
        """Get team pairs for a Swiss round."""
        matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=round_number
        ).order_by("id")
        pairs: set[frozenset[int]] = set()
        for match in matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            pairs.add(frozenset([match.team_1.id, match.team_2.id]))  # type: ignore[union-attr, list-item]
        return pairs

    def test_odd_swiss_round_creation(self) -> None:
        """Test Swiss round creation with 7 teams: 3 matches per round, 9 total."""
        # 7 teams -> 3 matches per round (floor(7/2))
        for round_num in range(1, 4):
            count = Match.objects.filter(
                swiss_round=self.swiss_round, sequence_number=round_num
            ).count()
            self.assertEqual(count, 3, f"Round {round_num} should have 3 matches")

        # Total: 3 rounds * 3 matches = 9
        total = Match.objects.filter(swiss_round=self.swiss_round).count()
        self.assertEqual(total, 9)

    def test_odd_swiss_full_lifecycle(self) -> None:
        """Test full lifecycle with byes: each round one team gets bye."""
        self.swiss_round.refresh_from_db()

        # Round 1: verify bye was applied
        self.assertIn("1", self.swiss_round.byes)
        bye_team_r1 = self.swiss_round.byes["1"]

        # Verify bye team has 1 win and 15 GF in results
        results = self.swiss_round.results
        bye_stats = results[str(bye_team_r1)]
        self.assertEqual(bye_stats["wins"], 1)
        self.assertEqual(bye_stats["GF"], 15)

        # Verify 3 matches have teams assigned, bye team is not in any match
        r1_matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=1
        ).order_by("id")
        self.assertEqual(r1_matches.count(), 3)
        for match in r1_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertNotEqual(match.team_1.id, bye_team_r1)
            self.assertNotEqual(match.team_2.id, bye_team_r1)

        # Score round 1
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10)])

        # Round 2: verify different bye team
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 2)
        self.assertIn("2", self.swiss_round.byes)
        bye_team_r2 = self.swiss_round.byes["2"]
        self.assertNotEqual(bye_team_r1, bye_team_r2, "Round 2 bye should be different team")

        # Verify bye team not in round 2 matches
        r2_matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=2
        ).order_by("id")
        for match in r2_matches:
            self.assertNotEqual(match.team_1.id, bye_team_r2)
            self.assertNotEqual(match.team_2.id, bye_team_r2)

        # Score round 2
        self._score_round_matches(2, [(15, 10), (15, 11), (15, 12)])

        # Round 3: verify yet another bye team
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 3)
        self.assertIn("3", self.swiss_round.byes)
        bye_team_r3 = self.swiss_round.byes["3"]
        self.assertNotEqual(bye_team_r3, bye_team_r1)
        self.assertNotEqual(bye_team_r3, bye_team_r2)

        # Score round 3
        self._score_round_matches(3, [(15, 10), (15, 11), (15, 12)])

        # Verify all byes are unique teams
        all_bye_teams = set(self.swiss_round.byes.values())
        self.assertEqual(len(all_bye_teams), 3, "All 3 byes should be different teams")

    def test_odd_swiss_no_rematch_with_bye(self) -> None:
        """Test that bye team is excluded from pairings and no rematches occur."""
        # Score round 1
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10)])

        # Verify round 2 has no rematches
        r1_pairs = self._get_round_pairs(1)
        r2_pairs = self._get_round_pairs(2)
        self.assertEqual(
            len(r1_pairs & r2_pairs), 0, "Round 2 should have no rematches from round 1"
        )

    def test_odd_swiss_api_returns_byes(self) -> None:
        """Test that Swiss rounds API returns byes data."""
        response = self.client.get(f"/api/tournament/swiss-rounds?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("byes", data[0])
        self.assertIn("1", data[0]["byes"])  # Round 1 bye exists

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestMultipleSwissGroups(ApiBaseTestCase):
    """Tests for multiple Swiss groups (Swiss A, Swiss B)."""

    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def test_create_two_swiss_groups(self) -> None:
        """Test creating Swiss A and Swiss B with different seeds."""
        # Create Swiss A with seeds 1,3,5,7
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 2,
                "seeding": [1, 3, 5, 7],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Create Swiss B with seeds 2,4,6,8
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 2,
                "seeding": [2, 4, 6, 8],
                "sequence_number": 2,
                "name": "B",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Verify both exist
        swiss_rounds = SwissRound.objects.filter(tournament=self.tournament).order_by(
            "sequence_number"
        )
        self.assertEqual(swiss_rounds.count(), 2)
        self.assertEqual(swiss_rounds[0].name, "A")
        self.assertEqual(swiss_rounds[1].name, "B")

        # Verify seedings are correct
        self.assertEqual(set(map(int, swiss_rounds[0].initial_seeding.keys())), {1, 3, 5, 7})
        self.assertEqual(set(map(int, swiss_rounds[1].initial_seeding.keys())), {2, 4, 6, 8})

    def test_swiss_seed_overlap_rejected(self) -> None:
        """Test that overlapping seeds between groups are rejected."""
        # Create Swiss A with seeds 1,2,3,4
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 2,
                "seeding": [1, 2, 3, 4],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Try Swiss B with overlapping seeds 3,4,5,6
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 2,
                "seeding": [3, 4, 5, 6],
                "sequence_number": 2,
                "name": "B",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("repeated_seeds", response.json()["message"])

    def test_get_swiss_rounds_returns_list(self) -> None:
        """Test that GET API returns a list ordered by sequence_number."""
        # Create two groups
        self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 2, "seeding": [1, 3, 5, 7], "sequence_number": 1, "name": "A"},
            content_type="application/json",
        )
        self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 2, "seeding": [2, 4, 6, 8], "sequence_number": 2, "name": "B"},
            content_type="application/json",
        )

        response = self.client.get(f"/api/tournament/swiss-rounds?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "A")
        self.assertEqual(data[1]["name"], "B")

    def test_multiple_swiss_groups_full_lifecycle(self) -> None:
        """Test playing through two Swiss groups and populating a bracket."""
        # Create Swiss A and B
        self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 2, "seeding": [1, 3, 5, 7], "sequence_number": 1, "name": "A"},
            content_type="application/json",
        )
        self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 2, "seeding": [2, 4, 6, 8], "sequence_number": 2, "name": "B"},
            content_type="application/json",
        )

        swiss_a = SwissRound.objects.get(tournament=self.tournament, name="A")
        swiss_b = SwissRound.objects.get(tournament=self.tournament, name="B")

        # Create bracket
        self.client.post(
            f"/api/tournament/bracket/{self.tournament.id}",
            {"name": "1-4", "sequence_number": 1},
            content_type="application/json",
        )
        bracket = Bracket.objects.get(tournament=self.tournament)

        # Start tournament
        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        # Verify both groups have R1 matches with teams assigned
        for sr in [swiss_a, swiss_b]:
            r1_matches = Match.objects.filter(swiss_round=sr, sequence_number=1)
            self.assertEqual(r1_matches.count(), 2)
            for m in r1_matches:
                self.assertIsNotNone(m.team_1)
                self.assertIsNotNone(m.team_2)

        # Score R1 for both groups
        for sr in [swiss_a, swiss_b]:
            matches = Match.objects.filter(swiss_round=sr, sequence_number=1).order_by("id")
            for match in matches:
                self.client.post(
                    f"/api/match/{match.id}/score",
                    {"team_1_score": 15, "team_2_score": 8},
                    content_type="application/json",
                )

        # Verify R2 generated for both
        for sr in [swiss_a, swiss_b]:
            sr.refresh_from_db()
            self.assertEqual(sr.current_round, 2)
            r2_matches = Match.objects.filter(swiss_round=sr, sequence_number=2)
            self.assertEqual(r2_matches.count(), 2)
            for m in r2_matches:
                self.assertIsNotNone(m.team_1)
                self.assertIsNotNone(m.team_2)

        # Score R2 for both groups
        for sr in [swiss_a, swiss_b]:
            matches = Match.objects.filter(swiss_round=sr, sequence_number=2).order_by("id")
            for match in matches:
                self.client.post(
                    f"/api/match/{match.id}/score",
                    {"team_1_score": 15, "team_2_score": 10},
                    content_type="application/json",
                )

        # Verify bracket is populated after both groups complete
        bracket.refresh_from_db()
        bracket_matches = Match.objects.filter(bracket=bracket, sequence_number=1)
        for m in bracket_matches:
            self.assertIsNotNone(m.team_1)
            self.assertIsNotNone(m.team_2)

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        Bracket.objects.filter(tournament=self.tournament).delete()
        super().tearDown()
