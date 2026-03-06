from typing import Any, cast

from server.tests.base import ApiBaseTestCase, add_teams_to_event, create_event, create_tournament
from server.tournament.models import Bracket, CrossPool, Match, PositionPool, SwissRound
from server.tournament.utils import rerun_swiss_round, sort_swiss_tied_teams


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
        expected_wins = 2
        four_pt_teams = [
            (tid, stats) for tid, stats in results.items() if stats["wins"] == expected_wins
        ]
        self.assertEqual(len(four_pt_teams), expected_wins, "Exactly 2 teams should have 2 wins")

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
        zero_win_teams = [(tid, stats) for tid, stats in results.items() if stats["wins"] == 0]
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
        r2_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=2).order_by(
            "id"
        )
        scores = [(10, 10)] + [(15, 11)] * (r2_matches.count() - 1)
        self._score_round_matches(2, scores)

        self.swiss_round.refresh_from_db()
        results = self.swiss_round.results

        # Find the draw match teams
        r2_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=2).order_by(
            "id"
        )
        draw_match = r2_matches[0]
        self.assertIsNotNone(draw_match.team_1)
        self.assertIsNotNone(draw_match.team_2)
        draw_t1 = draw_match.team_1.id  # type: ignore[union-attr]
        draw_t2 = draw_match.team_2.id  # type: ignore[union-attr]

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

        self.assertIsNotNone(pts_3_rank)
        self.assertIsNotNone(pts_2_rank)
        self.assertLess(
            pts_3_rank,  # type: ignore[arg-type]
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
        r1_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=1).order_by(
            "id"
        )
        self.assertEqual(r1_matches.count(), 3)
        for match in r1_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertNotEqual(match.team_1.id, bye_team_r1)  # type: ignore[union-attr]
            self.assertNotEqual(match.team_2.id, bye_team_r1)  # type: ignore[union-attr]

        # Score round 1
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10)])

        # Round 2: verify different bye team
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 2)
        self.assertIn("2", self.swiss_round.byes)
        bye_team_r2 = self.swiss_round.byes["2"]
        self.assertNotEqual(bye_team_r1, bye_team_r2, "Round 2 bye should be different team")

        # Verify bye team not in round 2 matches
        r2_matches = Match.objects.filter(swiss_round=self.swiss_round, sequence_number=2).order_by(
            "id"
        )
        for match in r2_matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            self.assertNotEqual(match.team_1.id, bye_team_r2)  # type: ignore[union-attr]
            self.assertNotEqual(match.team_2.id, bye_team_r2)  # type: ignore[union-attr]

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

    def test_rerun_recomputes_bye_when_no_games_played_in_round(self) -> None:
        """Rerun should be able to move the bye to the lowest-ranked eligible team when the round has no results yet."""
        self.swiss_round.refresh_from_db()

        # Start from a clean slate for this swiss round's matches so that
        # current_round has no COMPLETED matches and rerun can safely adjust the bye.
        Match.objects.filter(swiss_round=self.swiss_round).delete()

        team_ids = [team.id for team in self.teams]
        t1, t2, t3 = team_ids[0], team_ids[1], team_ids[2]

        # Construct results where t3 is clearly the worst team and t2 is mid-table.
        # We then simulate an incorrect bye already given to t2 in the current round.
        results: dict[int, dict[str, int]] = {
            t1: {"wins": 0, "losses": 0, "draws": 0, "GF": 20, "GA": 10},
            t2: {"wins": 0, "losses": 0, "draws": 0, "GF": 10, "GA": 10},
            t3: {"wins": 0, "losses": 0, "draws": 0, "GF": 5, "GA": 15},
        }
        for tid in team_ids[3:]:
            results[tid] = {"wins": 0, "losses": 0, "draws": 0, "GF": 10, "GA": 10}

        # Simulate that t2 has already been given a bye in round 2 (extra win).
        results[t2]["wins"] += 1

        self.swiss_round.results = results
        self.swiss_round.current_round = 2
        # Round 1 bye given to last team, round 2 (incorrectly) to t2.
        self.swiss_round.byes = {"1": team_ids[-1], "2": t2}
        self.swiss_round.save()

        # Use a simple current seeding mapping 1..7 -> team_ids so rerun can update it.
        self.tournament.current_seeding = {seed: team_ids[seed - 1] for seed in range(1, 8)}
        self.tournament.save()

        # When we rerun, we expect it to remove the round-2 bye from t2,
        # then (re)select the lowest-ranked eligible team (t3) as the new bye.
        rerun_swiss_round(self.tournament, self.swiss_round)

        self.swiss_round.refresh_from_db()
        final_results = {int(k): v for k, v in self.swiss_round.results.items()}

        self.assertEqual(
            int(self.swiss_round.byes["2"]),
            t3,
            "Rerun should move the bye to the lowest-ranked eligible team for the current round",
        )
        self.assertEqual(final_results[t2]["wins"], 0)
        self.assertEqual(final_results[t3]["wins"], 1)

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


class TestSwissCrossPoolBracketLifecycle(ApiBaseTestCase):
    """Test full lifecycle: 2 Swiss groups → Cross Pools → Bracket 1-8."""

    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Create Swiss A (seeds 1,3,5,7) and Swiss B (seeds 2,4,6,8)
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
        self.swiss_a = SwissRound.objects.get(tournament=self.tournament, name="A")
        self.swiss_b = SwissRound.objects.get(tournament=self.tournament, name="B")

        # Create cross pool with matches: 1v2, 3v4, 5v6, 7v8
        response = self.client.post(
            f"/api/tournament/cross-pool/{self.tournament.id}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.cross_pool = CrossPool.objects.get(tournament=self.tournament)

        cp_seeds = [(1, 2), (3, 4), (5, 6), (7, 8)]
        for seed_1, seed_2 in cp_seeds:
            Match.objects.create(
                tournament=self.tournament,
                cross_pool=self.cross_pool,
                sequence_number=1,
                placeholder_seed_1=seed_1,
                placeholder_seed_2=seed_2,
                name="Cross Pool",
            )

        # Create bracket 1-8
        response = self.client.post(
            f"/api/tournament/bracket/{self.tournament.id}",
            {"name": "1-8", "sequence_number": 1},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.bracket = Bracket.objects.get(tournament=self.tournament)

        # Start tournament
        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

    def _score_swiss_round(self, swiss_round: SwissRound, round_number: int) -> None:
        """Score all matches in a swiss round with higher seeds winning."""
        matches = Match.objects.filter(
            swiss_round=swiss_round, sequence_number=round_number
        ).order_by("id")
        for match in matches:
            self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 10},
                content_type="application/json",
            )

    def test_full_swiss_cp_bracket_lifecycle(self) -> None:
        """
        Test full lifecycle:
        1. Play 2 rounds of Swiss A and Swiss B
        2. Cross pool matches get populated and played
        3. Bracket matches get populated and played
        4. Tournament completes
        """
        # Step 1: Play Swiss rounds
        for swiss_round in [self.swiss_a, self.swiss_b]:
            self._score_swiss_round(swiss_round, 1)

        # Verify R2 generated
        for swiss_round in [self.swiss_a, self.swiss_b]:
            swiss_round.refresh_from_db()
            self.assertEqual(swiss_round.current_round, 2)

        for swiss_round in [self.swiss_a, self.swiss_b]:
            self._score_swiss_round(swiss_round, 2)

        # Verify round_results snapshots were created
        for swiss_round in [self.swiss_a, self.swiss_b]:
            swiss_round.refresh_from_db()
            self.assertIn("1", swiss_round.round_results)
            self.assertIn("2", swiss_round.round_results)

        # Step 2: Cross pool matches should be populated with teams
        cp_matches = Match.objects.filter(cross_pool=self.cross_pool).order_by("id")
        self.assertEqual(cp_matches.count(), 4)
        for match in cp_matches:
            self.assertIsNotNone(match.team_1, f"CP match {match.id} missing team_1")
            self.assertIsNotNone(match.team_2, f"CP match {match.id} missing team_2")
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        # Score cross pool matches: higher seed wins
        for match in cp_matches:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 12},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Step 3: Bracket should be populated
        bracket_r1 = Match.objects.filter(bracket=self.bracket, sequence_number=1).order_by("id")
        for match in bracket_r1:
            self.assertIsNotNone(match.team_1, f"Bracket match {match.id} missing team_1")
            self.assertIsNotNone(match.team_2, f"Bracket match {match.id} missing team_2")

        # Score bracket quarter finals
        for match in bracket_r1:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 11},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Score bracket semi finals
        bracket_r2 = Match.objects.filter(bracket=self.bracket, sequence_number=2).order_by("id")
        for match in bracket_r2:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 12},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Score bracket finals (seq 3)
        bracket_r3 = Match.objects.filter(bracket=self.bracket, sequence_number=3).order_by("id")
        for match in bracket_r3:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 13},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Step 4: Tournament should be complete
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.status, "COM")

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        CrossPool.objects.filter(tournament=self.tournament).delete()
        Bracket.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestSwissCPPositionPoolBracketLifecycle(ApiBaseTestCase):
    """Test: 2 Swiss groups → CP (1v2, 3v4) + Position Pool 5-8 → Bracket 1-4."""

    def setUp(self) -> None:
        super().setUp()

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        # Create Swiss A (seeds 1,3,5,7) and Swiss B (seeds 2,4,6,8)
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
        self.swiss_a = SwissRound.objects.get(tournament=self.tournament, name="A")
        self.swiss_b = SwissRound.objects.get(tournament=self.tournament, name="B")

        # Create cross pool with matches: 1v2, 3v4
        response = self.client.post(
            f"/api/tournament/cross-pool/{self.tournament.id}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.cross_pool = CrossPool.objects.get(tournament=self.tournament)

        for seed_1, seed_2 in [(1, 2), (3, 4)]:
            Match.objects.create(
                tournament=self.tournament,
                cross_pool=self.cross_pool,
                sequence_number=1,
                placeholder_seed_1=seed_1,
                placeholder_seed_2=seed_2,
                name="Cross Pool",
            )

        # Create position pool for seeds 5-8
        response = self.client.post(
            f"/api/tournament/position-pool/{self.tournament.id}",
            {"name": "PP", "seeding": [5, 6, 7, 8], "sequence_number": 1},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.position_pool = PositionPool.objects.get(tournament=self.tournament)

        # Create bracket 1-4
        response = self.client.post(
            f"/api/tournament/bracket/{self.tournament.id}",
            {"name": "1-4", "sequence_number": 1},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.bracket = Bracket.objects.get(tournament=self.tournament)

        # Start tournament
        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

    def _score_swiss_round(self, swiss_round: SwissRound, round_number: int) -> None:
        """Score all matches in a swiss round with higher seeds winning."""
        matches = Match.objects.filter(
            swiss_round=swiss_round, sequence_number=round_number
        ).order_by("id")
        for match in matches:
            self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 10},
                content_type="application/json",
            )

    def test_full_swiss_cp_pp_bracket_lifecycle(self) -> None:
        """
        Test full lifecycle:
        1. Play 2 rounds of Swiss A and Swiss B
        2. CP (1v2, 3v4) and Position Pool 5-8 get populated simultaneously
        3. Play CP and position pool matches
        4. Bracket 1-4 gets populated from CP results
        5. Play bracket through to completion
        """
        # Step 1: Play Swiss rounds
        for swiss_round in [self.swiss_a, self.swiss_b]:
            self._score_swiss_round(swiss_round, 1)

        for swiss_round in [self.swiss_a, self.swiss_b]:
            swiss_round.refresh_from_db()
            self.assertEqual(swiss_round.current_round, 2)

        for swiss_round in [self.swiss_a, self.swiss_b]:
            self._score_swiss_round(swiss_round, 2)

        # Step 2: Both CP and position pool should be populated
        cp_matches = Match.objects.filter(cross_pool=self.cross_pool).order_by("id")
        self.assertEqual(cp_matches.count(), 2)
        for match in cp_matches:
            self.assertIsNotNone(match.team_1, f"CP match {match.id} missing team_1")
            self.assertIsNotNone(match.team_2, f"CP match {match.id} missing team_2")
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        pp_matches = Match.objects.filter(position_pool=self.position_pool).order_by("id")
        # 4 teams round robin = 6 matches
        self.assertEqual(pp_matches.count(), 6)
        for match in pp_matches:
            self.assertIsNotNone(match.team_1, f"PP match {match.id} missing team_1")
            self.assertIsNotNone(match.team_2, f"PP match {match.id} missing team_2")
            self.assertEqual(match.status, Match.Status.SCHEDULED)

        # Step 3: Score CP matches (higher seed wins)
        for match in cp_matches:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 12},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Score position pool matches
        pp_scores = [(15, 10), (15, 8), (15, 7), (13, 15), (15, 10), (15, 12)]
        for match, score in zip(pp_matches, pp_scores, strict=True):
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": score[0], "team_2_score": score[1]},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Step 4: Bracket 1-4 should be populated after CP completes
        bracket_r1 = Match.objects.filter(bracket=self.bracket, sequence_number=1).order_by("id")
        for match in bracket_r1:
            self.assertIsNotNone(match.team_1, f"Bracket match {match.id} missing team_1")
            self.assertIsNotNone(match.team_2, f"Bracket match {match.id} missing team_2")

        # Score bracket semi finals
        for match in bracket_r1:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 11},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Score bracket finals + 3rd place
        bracket_r2 = Match.objects.filter(bracket=self.bracket, sequence_number=2).order_by("id")
        for match in bracket_r2:
            response = self.client.post(
                f"/api/match/{match.id}/score",
                {"team_1_score": 15, "team_2_score": 13},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        # Step 5: Tournament should be complete
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.status, "COM")

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        CrossPool.objects.filter(tournament=self.tournament).delete()
        PositionPool.objects.filter(tournament=self.tournament).delete()
        Bracket.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestSwissTiebreakerRecursiveH2H(ApiBaseTestCase):
    """Test that 3-way H2H ties are resolved by recursive sub-group tiebreaking.

    Production bug: 3 teams tied on points (A, B, C). A beat B, B beat C,
    A-C didn't play. H2H wins: A=1, B=1, C=0. Without recursive fix,
    A and B fall to OS/GD tiebreaker. With fix, recursive call on {A,B}
    finds A beat B → A > B > C.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def _create_swiss_round(self, name: str = "A") -> SwissRound:
        """Helper to create a swiss round with empty results for all teams."""
        initial_seeding = {str(i): self.teams[i - 1].id for i in range(1, 9)}
        results = {
            str(self.teams[i - 1].id): {
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "GF": 0,
                "GA": 0,
            }
            for i in range(1, 9)
        }
        return SwissRound.objects.create(
            tournament=self.tournament,
            name=name,
            sequence_number=1,
            num_rounds=3,
            current_round=3,
            initial_seeding=initial_seeding,
            results=results,
        )

    def test_three_way_tie_recursive_h2h(self) -> None:
        """A beats B, B beats C, A-C didn't play. All tied on points.

        Expected ranking: A > B > C (A beat B in direct H2H after recursive call).
        B should NOT rank above A just because B has better GD.
        """
        swiss_round = self._create_swiss_round()

        team_a = self.teams[0]  # Seed 1
        team_b = self.teams[1]  # Seed 2
        team_c = self.teams[2]  # Seed 3

        # Create completed matches: A beats B, B beats C, A-C don't play
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=1,
            team_1=team_a,
            team_2=team_b,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=2,
            team_1=team_b,
            team_2=team_c,
            score_team_1=15,
            score_team_2=8,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=2,
            placeholder_seed_2=3,
        )

        # Give each team additional matches against other teams so all end up 2W-1L
        team_d = self.teams[3]
        team_e = self.teams[4]
        team_f = self.teams[5]

        # A lost to D (so A is 1W-1L before last match)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=2,
            team_1=team_a,
            team_2=team_d,
            score_team_1=8,
            score_team_2=15,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=1,
            placeholder_seed_2=4,
        )
        # A beats E (A goes to 2W-1L)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=3,
            team_1=team_a,
            team_2=team_e,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=1,
            placeholder_seed_2=5,
        )

        # B lost to F (so B goes to 2W-1L)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=3,
            team_1=team_b,
            team_2=team_f,
            score_team_1=8,
            score_team_2=15,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=2,
            placeholder_seed_2=6,
        )

        # C beats D (C gets a win)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=1,
            team_1=team_c,
            team_2=team_d,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=3,
            placeholder_seed_2=4,
        )
        # C lost to E (C goes to 2W-1L)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=3,
            team_1=team_c,
            team_2=team_e,
            score_team_1=8,
            score_team_2=15,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=3,
            placeholder_seed_2=5,
        )

        # Build results: all three at 2W-1L (4pts)
        # Give B higher GD than A to verify recursive H2H overrides GD
        all_results: dict[int, dict[str, int]] = {
            team_a.id: {"id": team_a.id, "wins": 2, "losses": 1, "draws": 0, "GF": 38, "GA": 35},
            team_b.id: {"id": team_b.id, "wins": 2, "losses": 1, "draws": 0, "GF": 38, "GA": 25},
            team_c.id: {"id": team_c.id, "wins": 2, "losses": 1, "draws": 0, "GF": 38, "GA": 33},
        }

        tied_teams = list(all_results.values())

        result = sort_swiss_tied_teams(tied_teams, all_results, swiss_round)

        # A should be first (beat B in recursive H2H), then B (beat C), then C
        self.assertEqual(result[0]["id"], team_a.id, "A should rank 1st (beat B in direct H2H)")
        self.assertEqual(result[1]["id"], team_b.id, "B should rank 2nd (beat C in direct H2H)")
        self.assertEqual(result[2]["id"], team_c.id, "C should rank 3rd")

    def test_three_way_tie_all_equal_h2h_falls_to_os_then_gd(self) -> None:
        """When all 3 teams have equal H2H wins, recursion stops and falls to OS, then GD.

        Circular H2H: A beats B, B beats C, C beats A → each has 1 H2H win.
        Each also plays one match against a different-strength opponent:
        - A played D (3W, strong) → A gets high OS
        - B played E (1W, medium) → B gets medium OS
        - C played F (0W, weak) → C gets low OS
        C has the best GD but worst OS → verifies OS takes precedence over GD.
        """
        swiss_round = self._create_swiss_round()

        team_a = self.teams[0]
        team_b = self.teams[1]
        team_c = self.teams[2]
        team_d = self.teams[3]  # Strong opponent (3W)
        team_e = self.teams[4]  # Medium opponent (1W)
        team_f = self.teams[5]  # Weak opponent (0W)

        # Circular H2H: A beats B, B beats C, C beats A → each has 1 H2H win
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=1,
            team_1=team_a,
            team_2=team_b,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=2,
            team_1=team_b,
            team_2=team_c,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=2,
            placeholder_seed_2=3,
        )
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=3,
            team_1=team_c,
            team_2=team_a,
            score_team_1=15,
            score_team_2=10,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=3,
            placeholder_seed_2=1,
        )

        # Extra matches to differentiate OS:
        # A beats D (strong, 3W)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=2,
            team_1=team_a,
            team_2=team_d,
            score_team_1=15,
            score_team_2=14,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=1,
            placeholder_seed_2=4,
        )
        # B beats E (medium, 1W)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=1,
            team_1=team_b,
            team_2=team_e,
            score_team_1=15,
            score_team_2=14,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=2,
            placeholder_seed_2=5,
        )
        # C beats F (weak, 0W)
        Match.objects.create(
            tournament=self.tournament,
            swiss_round=swiss_round,
            sequence_number=1,
            team_1=team_c,
            team_2=team_f,
            score_team_1=15,
            score_team_2=14,
            status=Match.Status.COMPLETED,
            placeholder_seed_1=3,
            placeholder_seed_2=6,
        )

        # All three at 2W-1L (4pts). C has best GD, A has worst.
        # OS should override GD: A faced strongest opponents, C faced weakest.
        all_results: dict[int, dict[str, int]] = {
            team_a.id: {"id": team_a.id, "wins": 2, "losses": 1, "draws": 0, "GF": 30, "GA": 30},
            team_b.id: {"id": team_b.id, "wins": 2, "losses": 1, "draws": 0, "GF": 35, "GA": 30},
            team_c.id: {"id": team_c.id, "wins": 2, "losses": 1, "draws": 0, "GF": 40, "GA": 30},
            team_d.id: {"id": team_d.id, "wins": 3, "losses": 0, "draws": 0, "GF": 45, "GA": 20},
            team_e.id: {"id": team_e.id, "wins": 1, "losses": 2, "draws": 0, "GF": 25, "GA": 35},
            team_f.id: {"id": team_f.id, "wins": 0, "losses": 3, "draws": 0, "GF": 15, "GA": 45},
        }

        tied_teams = [all_results[team_a.id], all_results[team_b.id], all_results[team_c.id]]

        result = sort_swiss_tied_teams(tied_teams, all_results, swiss_round)

        # All have 1 H2H win → recursion stops (sub_group == tied_teams)
        # OS: A faced D(6pts)+B(4pts)+C(4pts)=14, B faced A(4pts)+C(4pts)+E(2pts)=10,
        #     C faced B(4pts)+A(4pts)+F(0pts)=8
        # A (OS=14) > B (OS=10) > C (OS=8), even though C has best GD
        self.assertEqual(result[0]["id"], team_a.id, "A first by OS (faced strongest opponents)")
        self.assertEqual(result[1]["id"], team_b.id, "B second by OS")
        self.assertEqual(result[2]["id"], team_c.id, "C third by OS (despite best GD)")

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestSwissNoRematch4Rounds(ApiBaseTestCase):
    """Test that 8 teams over 4 rounds produces no rematches."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 4,
                "seeding": [1, 2, 3, 4, 5, 6, 7, 8],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.swiss_round = SwissRound.objects.get(tournament=self.tournament)

        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

    def _score_round_matches(self, round_number: int, scores: list[tuple[int, int]]) -> None:
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
        matches = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=round_number
        ).order_by("id")
        pairs: set[frozenset[int]] = set()
        for match in matches:
            self.assertIsNotNone(match.team_1)
            self.assertIsNotNone(match.team_2)
            pairs.add(frozenset([match.team_1.id, match.team_2.id]))  # type: ignore[union-attr, list-item]
        return pairs

    def test_no_rematches_across_4_rounds(self) -> None:
        """8 teams, 4 rounds — every round should have unique matchups."""
        # R1: higher seeds win with varying margins
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10), (15, 11)])
        # R2: mix of results
        self._score_round_matches(2, [(15, 10), (15, 12), (15, 13), (15, 14)])
        # R3
        self._score_round_matches(3, [(15, 11), (15, 9), (15, 13), (15, 10)])

        # Collect all pairs from rounds 1-3
        all_pairs: set[frozenset[int]] = set()
        for r in range(1, 4):
            round_pairs = self._get_round_pairs(r)
            all_pairs |= round_pairs

        # R4 should exist and have no rematches
        r4_pairs = self._get_round_pairs(4)
        self.assertEqual(len(r4_pairs), 4, "R4 should have 4 matches")

        rematches = all_pairs & r4_pairs
        self.assertEqual(len(rematches), 0, f"R4 should have no rematches, but found: {rematches}")

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        super().tearDown()


class TestSwissRerun(ApiBaseTestCase):
    """Test that rerun fixes corrupted rankings and rematch pairings."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {
                "num_rounds": 4,
                "seeding": [1, 2, 3, 4, 5, 6, 7, 8],
                "sequence_number": 1,
                "name": "A",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.swiss_round = SwissRound.objects.get(tournament=self.tournament)

        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

    def _score_round_matches(self, round_number: int, scores: list[tuple[int, int]]) -> None:
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

    def test_rerun_fixes_corrupted_rankings_and_rematches(self) -> None:
        """Simulate stale rankings + rematch, then rerun to fix both."""
        # Play R1-R3 normally
        self._score_round_matches(1, [(15, 8), (15, 9), (15, 10), (15, 11)])
        self._score_round_matches(2, [(15, 10), (15, 12), (15, 13), (15, 14)])
        self._score_round_matches(3, [(15, 11), (15, 9), (15, 13), (15, 10)])

        # R4 matches should now be SCHEDULED
        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.current_round, 4)

        r4_matches = list(
            Match.objects.filter(
                swiss_round=self.swiss_round, sequence_number=4, status=Match.Status.SCHEDULED
            ).order_by("id")
        )
        self.assertEqual(len(r4_matches), 4)

        # Collect R1-R3 pairs to find a rematch candidate
        prev_pairs: set[frozenset[int]] = set()
        for r in range(1, 4):
            for m in Match.objects.filter(swiss_round=self.swiss_round, sequence_number=r):
                if m.team_1 and m.team_2:
                    prev_pairs.add(frozenset([m.team_1.id, m.team_2.id]))

        # Corrupt R4: force R4 match 0 to have same teams as R1 match 0 (rematch)
        r1_match = (
            Match.objects.filter(swiss_round=self.swiss_round, sequence_number=1)
            .order_by("id")
            .first()
        )
        self.assertIsNotNone(r1_match)
        self.assertIsNotNone(r1_match.team_1)  # type: ignore[union-attr]
        self.assertIsNotNone(r1_match.team_2)  # type: ignore[union-attr]

        # Django field typing in tests can surface as Field descriptors to mypy;
        # treat these as runtime values for corruption setup.
        r1_match_any = cast(Any, r1_match)
        r4_matches[0].team_1_id = r1_match_any.team_1_id
        r4_matches[0].team_2_id = r1_match_any.team_2_id
        r4_matches[0].save()

        # Also corrupt rankings: swap rank 1 and rank 2
        results = {int(k): v for k, v in self.swiss_round.results.items()}
        team_ids_by_rank = sorted(results, key=lambda tid: results[tid]["rank"])
        rank1_tid = team_ids_by_rank[0]
        rank2_tid = team_ids_by_rank[1]
        results[rank1_tid]["rank"], results[rank2_tid]["rank"] = (
            results[rank2_tid]["rank"],
            results[rank1_tid]["rank"],
        )
        self.swiss_round.results = results
        self.swiss_round.save()

        # Verify corruption: R4 now has a rematch
        corrupted_r4_pairs: set[frozenset[int]] = set()
        for m in Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=4, status=Match.Status.SCHEDULED
        ):
            if m.team_1 and m.team_2:
                corrupted_r4_pairs.add(frozenset([m.team_1.id, m.team_2.id]))
        self.assertTrue(
            len(prev_pairs & corrupted_r4_pairs) > 0, "Corruption should create a rematch"
        )

        # Verify corruption: rankings are swapped
        self.swiss_round.refresh_from_db()
        corrupted_results = {int(k): v for k, v in self.swiss_round.results.items()}
        self.assertEqual(corrupted_results[rank1_tid]["rank"], 2)
        self.assertEqual(corrupted_results[rank2_tid]["rank"], 1)

        # Call rerun API
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.swiss_round.id}/rerun",
        )
        self.assertEqual(response.status_code, 200)

        # Verify rankings are fixed
        self.swiss_round.refresh_from_db()
        fixed_results = {int(k): v for k, v in self.swiss_round.results.items()}
        self.assertEqual(fixed_results[rank1_tid]["rank"], 1, "Rank 1 should be restored")
        self.assertEqual(fixed_results[rank2_tid]["rank"], 2, "Rank 2 should be restored")

        # Verify R4 has no rematches
        fixed_r4_pairs: set[frozenset[int]] = set()
        for m in Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=4, status=Match.Status.SCHEDULED
        ):
            if m.team_1 and m.team_2:
                fixed_r4_pairs.add(frozenset([m.team_1.id, m.team_2.id]))

        rematches = prev_pairs & fixed_r4_pairs
        self.assertEqual(len(rematches), 0, f"Rerun should fix rematches, but found: {rematches}")

        # Verify completed matches (R1-R3) are untouched
        for r in range(1, 4):
            completed = Match.objects.filter(
                swiss_round=self.swiss_round, sequence_number=r, status=Match.Status.COMPLETED
            )
            self.assertEqual(completed.count(), 4, f"R{r} should still have 4 completed matches")

        # Verify R4 matches still have SCHEDULED status (metadata preserved)
        r4_scheduled = Match.objects.filter(
            swiss_round=self.swiss_round, sequence_number=4, status=Match.Status.SCHEDULED
        )
        self.assertEqual(r4_scheduled.count(), 4, "R4 should still have 4 SCHEDULED matches")

    def tearDown(self) -> None:
        Match.objects.filter(tournament=self.tournament).delete()
        SwissRound.objects.filter(tournament=self.tournament).delete()
        super().tearDown()
