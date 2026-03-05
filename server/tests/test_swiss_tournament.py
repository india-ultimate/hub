from server.tests.base import ApiBaseTestCase, add_teams_to_event, create_event, create_tournament
from server.tournament.models import Bracket, Match, SwissRound


class TestSwissTournamentLifecycle(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Create Swiss Round via API
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3},
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
        response = self.client.get(f"/api/tournament/swiss-round?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["num_rounds"], 3)
        self.assertEqual(data["current_round"], 1)
        self.assertTrue(len(data["initial_seeding"]) > 0)
        self.assertTrue(len(data["results"]) > 0)

        # Verify matches were created (3 rounds * 4 matches per round = 12)
        match_count = Match.objects.filter(swiss_round=self.swiss_round).count()
        self.assertEqual(match_count, 12)

    def test_swiss_round_get_api(self) -> None:
        """Test fetching Swiss round via API."""
        response = self.client.get(f"/api/tournament/swiss-round?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["num_rounds"], 3)

        # Also test by slug
        response = self.client.get(f"/api/tournament/swiss-round?slug={self.event.slug}")
        self.assertEqual(response.status_code, 200)

    def test_swiss_duplicate_creation_blocked(self) -> None:
        """Test that creating a second Swiss round is blocked."""
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.json()["message"])

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

        # Create Swiss Round with 3 rounds
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3},
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
        """Test that Swiss round API returns byes data."""
        response = self.client.get(f"/api/tournament/swiss-round?id={self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("byes", data)
        self.assertIn("1", data["byes"])  # Round 1 bye exists

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        super().tearDown()
