"""Tests for pre-start seeding re-sync."""

from server.tests.base import ApiBaseTestCase
from server.tournament.models import Match, Pool, SwissRound


class SeedingUpdateResyncTests(ApiBaseTestCase):
    """Re-seeding before the tournament starts must re-sync pool snapshots."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        for name, seeds in (("A", [1, 4, 5, 8]), ("B", [2, 3, 6, 7])):
            response = self.client.post(
                f"/api/tournament/pool/{self.tournament.id}",
                {
                    "name": name,
                    "sequence_number": 1 if name == "A" else 2,
                    "seeding": seeds,
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
        self.pool_a = Pool.objects.get(tournament=self.tournament, name="A")
        self.pool_b = Pool.objects.get(tournament=self.tournament, name="B")

    def _swapped_seeding(self) -> dict[str, int]:
        """Original seeding with seeds 1 and 2 swapped."""
        seeding = {str(k): v for k, v in self.tournament.initial_seeding.items()}
        seeding["1"], seeding["2"] = seeding["2"], seeding["1"]
        return seeding

    def test_reseed_resyncs_pool_teams(self) -> None:
        original_seed_1_team = self.tournament.initial_seeding["1"]
        original_seed_2_team = self.tournament.initial_seeding["2"]

        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": self._swapped_seeding()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.pool_a.refresh_from_db()
        self.pool_b.refresh_from_db()
        # Seed 1 lives in pool A, seed 2 in pool B; both must now point at the
        # swapped teams, with results re-keyed to the new team ids.
        self.assertEqual(self.pool_a.initial_seeding["1"], original_seed_2_team)
        self.assertEqual(self.pool_b.initial_seeding["2"], original_seed_1_team)
        self.assertIn(str(original_seed_2_team), self.pool_a.results)
        self.assertNotIn(str(original_seed_1_team), self.pool_a.results)
        self.assertEqual(sorted(row["rank"] for row in self.pool_a.results.values()), [1, 2, 3, 4])

    def test_reseed_keeps_matches_as_placeholders(self) -> None:
        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": self._swapped_seeding()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        for match in Match.objects.filter(tournament=self.tournament):
            self.assertIsNone(match.team_1)
            self.assertIsNone(match.team_2)
            self.assertEqual(match.status, Match.Status.YET_TO_FIX)

    def test_start_after_reseed_assigns_new_teams(self) -> None:
        original_seed_2_team = self.tournament.initial_seeding["2"]
        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": self._swapped_seeding()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        # The seed-1 vs seed-4 match in pool A must feature the new seed-1 team
        match = Match.objects.get(
            tournament=self.tournament,
            pool=self.pool_a,
            placeholder_seed_1=1,
            placeholder_seed_2=4,
        )
        self.assertEqual(match.team_1_id, original_seed_2_team)

    def test_reseed_blocked_after_start(self) -> None:
        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": self._swapped_seeding()},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("after the tournament has started", response.json()["message"])

    def test_invalid_seeding_still_rejected(self) -> None:
        seeding = self._swapped_seeding()
        seeding.pop("8")
        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": seeding},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class SeedingUpdateResyncSwissTests(ApiBaseTestCase):
    """Re-seeding must also re-sync Swiss group snapshots."""

    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

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

    def test_reseed_resyncs_swiss_group(self) -> None:
        original_seed_1_team = self.tournament.initial_seeding["1"]
        original_seed_2_team = self.tournament.initial_seeding["2"]
        seeding = {str(k): v for k, v in self.tournament.initial_seeding.items()}
        seeding["1"], seeding["2"] = seeding["2"], seeding["1"]

        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": seeding},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self.swiss_round.refresh_from_db()
        self.assertEqual(self.swiss_round.initial_seeding["1"], original_seed_2_team)
        self.assertEqual(self.swiss_round.initial_seeding["2"], original_seed_1_team)
        self.assertIn(str(original_seed_1_team), self.swiss_round.results)
        self.assertEqual(self.swiss_round.results[str(original_seed_2_team)]["rank"], 1)
        self.assertEqual(self.swiss_round.results[str(original_seed_2_team)]["opp_strength"], 0)

    def test_start_after_reseed_assigns_new_teams_to_round_one(self) -> None:
        original_seed_2_team = self.tournament.initial_seeding["2"]
        seeding = {str(k): v for k, v in self.tournament.initial_seeding.items()}
        seeding["1"], seeding["2"] = seeding["2"], seeding["1"]

        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": seeding},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(f"/api/tournament/start/{self.tournament.id}")
        self.assertEqual(response.status_code, 200)

        # Round 1 pairs 1 vs 8; team at seed 1 must be the swapped team
        match = Match.objects.get(
            tournament=self.tournament,
            swiss_round=self.swiss_round,
            placeholder_seed_1=1,
            placeholder_seed_2=8,
        )
        self.assertEqual(match.team_1_id, original_seed_2_team)
