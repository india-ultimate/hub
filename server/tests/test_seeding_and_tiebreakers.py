"""Tests for pre-start seeding re-sync and WFDF-style tie-breaker fixes."""

from typing import Any

from server.core.models import Team
from server.tests.base import ApiBaseTestCase
from server.tournament.models import Bracket, Match, Pool, PositionPool, SwissRound, Tournament
from server.tournament.utils import (
    apply_bye,
    get_new_pool_results,
    recompute_swiss_ranks,
    sort_swiss_tied_teams,
    sort_tied_teams,
    update_tournament_seeding,
    validate_bracket_name,
)


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
                {"name": name, "sequence_number": 1 if name == "A" else 2, "seeding": seeds},
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
            tournament=self.tournament, pool=self.pool_a, placeholder_seed_1=1, placeholder_seed_2=4
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


class AgentSeedingProposalTests(ApiBaseTestCase):
    """The agent's update-seeding proposal shares the same guarded util."""

    def test_util_rejects_started_tournament(self) -> None:
        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()
        ok, error = update_tournament_seeding(
            self.tournament, {int(k): v for k, v in self.tournament.initial_seeding.items()}
        )
        self.assertFalse(ok)
        self.assertIn("after the tournament has started", (error or {}).get("message", ""))

    def test_util_rejects_invalid_seeding(self) -> None:
        seeding = {int(k): v for k, v in self.tournament.initial_seeding.items()}
        seeding.pop(8)
        ok, error = update_tournament_seeding(self.tournament, seeding)
        self.assertFalse(ok)
        self.assertIn("errors", (error or {}).get("message", ""))

    def test_agent_proposal_apply_goes_through_guard(self) -> None:
        from server.core.models import User
        from server.tournament_agent.models import TournamentAgentSession
        from server.tournament_agent.services.proposals import ProposalApplyError, apply_proposal
        from server.tournament_agent.tools import ToolContext, propose_update_seeding

        staff = User.objects.create(username="agent-staff", is_staff=True)
        session = TournamentAgentSession.objects.create(
            user=staff, tournament=self.tournament, model_id="minimax-m3"
        )
        ctx = ToolContext(session=session, tournament=self.tournament)

        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()

        from server.tournament_agent.models import AgentProposal

        result = propose_update_seeding(
            ctx, seeding={str(k): v for k, v in self.tournament.initial_seeding.items()}
        )
        proposal = AgentProposal.objects.get(id=result["proposal_id"])
        with self.assertRaises(ProposalApplyError):
            apply_proposal(proposal)


class PoolThreeWayTieBreakTests(ApiBaseTestCase):
    """WFDF restart: once a criterion separates teams, remaining ties restart at H2H."""

    def setUp(self) -> None:
        super().setUp()
        self.team_a, self.team_b, self.team_c, self.team_d = self.teams[:4]
        self.pool = Pool.objects.create(
            name="A",
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding={
                1: self.team_a.id,
                2: self.team_b.id,
                3: self.team_c.id,
                4: self.team_d.id,
            },
            results={},
        )

    def _play(self, team_1: Team, team_2: Team, score_1: int, score_2: int, **kwargs: Any) -> Match:
        return Match.objects.create(
            tournament=self.tournament,
            team_1=team_1,
            team_2=team_2,
            score_team_1=score_1,
            score_team_2=score_2,
            status=Match.Status.COMPLETED,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            **kwargs,
        )

    def _run_pool(self, matches: list[Match]) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
        results = {
            team.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0}
            for team in (self.team_a, self.team_b, self.team_c, self.team_d)
        }
        seeding = {1: 0, 2: 0, 3: 0, 4: 0}
        for match in matches:
            results, seeding = get_new_pool_results(results, match, [1, 2, 3, 4], seeding)
        return results, seeding

    def test_three_way_tie_restarts_at_head_to_head(self) -> None:
        """A/B/C cycle with equal H2H GD; overall GD separates A; then C>B by H2H.

        The old single-pass sort left B ahead of C (input order) because
        every remaining criterion was equal; WFDF requires restarting at
        head-to-head between B and C, which C won.
        """
        matches = [
            self._play(self.team_a, self.team_b, 10, 15, pool=self.pool),  # B beats A
            self._play(self.team_b, self.team_c, 10, 15, pool=self.pool),  # C beats B
            self._play(self.team_c, self.team_a, 10, 15, pool=self.pool),  # A beats C
            self._play(self.team_a, self.team_d, 15, 5, pool=self.pool),  # A +10
            self._play(self.team_b, self.team_d, 15, 10, pool=self.pool),  # B +5
            self._play(self.team_c, self.team_d, 15, 10, pool=self.pool),  # C +5
        ]
        results, seeding = self._run_pool(matches)

        self.assertEqual(results[self.team_a.id]["rank"], 1)  # best overall GD
        self.assertEqual(results[self.team_c.id]["rank"], 2)  # beat B head-to-head
        self.assertEqual(results[self.team_b.id]["rank"], 3)
        self.assertEqual(results[self.team_d.id]["rank"], 4)
        self.assertEqual(seeding[2], self.team_c.id)

    def test_head_to_head_ignores_matches_from_other_stages(self) -> None:
        """A bracket game between two pool-tied teams must not affect pool ranks."""
        # Pool: A beats B and D, loses to C; B beats C and D, loses to A.
        matches = [
            self._play(self.team_a, self.team_b, 15, 14, pool=self.pool),
            self._play(self.team_c, self.team_a, 15, 10, pool=self.pool),
            self._play(self.team_a, self.team_d, 15, 10, pool=self.pool),
            self._play(self.team_b, self.team_c, 15, 10, pool=self.pool),
            self._play(self.team_b, self.team_d, 15, 10, pool=self.pool),
            self._play(self.team_d, self.team_c, 15, 10, pool=self.pool),
        ]
        # Same-tournament bracket game where B crushed A. If it leaked into the
        # pool tie-break, B would jump ahead of A.
        bracket = Bracket.objects.create(
            name="1-4",
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding={1: 0, 2: 0, 3: 0, 4: 0},
            current_seeding={1: 0, 2: 0, 3: 0, 4: 0},
        )
        self._play(self.team_a, self.team_b, 0, 15, bracket=bracket)

        results, _ = self._run_pool(matches)

        self.assertEqual(results[self.team_a.id]["rank"], 1)  # won pool H2H vs B
        self.assertEqual(results[self.team_b.id]["rank"], 2)
        self.assertEqual(results[self.team_d.id]["rank"], 3)  # won pool H2H vs C
        self.assertEqual(results[self.team_c.id]["rank"], 4)

    def test_position_pool_head_to_head_ignores_pool_games(self) -> None:
        """Position pool ties must only count position pool games."""
        position_pool = PositionPool.objects.create(
            name="E",
            tournament=self.tournament,
            sequence_number=1,
            initial_seeding={5: 0, 6: 0, 7: 0},
            results={},
        )
        # Earlier pool game: C thrashed B. Must not leak into position pool.
        self._play(self.team_c, self.team_b, 15, 0, pool=self.pool)

        pp_matches = [
            # Cycle: A beats B (+1), B beats C (+5), C beats A (+2)
            self._play(self.team_a, self.team_b, 15, 14, position_pool=position_pool),
            self._play(self.team_b, self.team_c, 15, 10, position_pool=position_pool),
            self._play(self.team_c, self.team_a, 15, 13, position_pool=position_pool),
        ]
        results = {
            team.id: {"wins": 0, "losses": 0, "draws": 0, "GF": 0, "GA": 0}
            for team in (self.team_a, self.team_b, self.team_c)
        }
        seeding = {5: 0, 6: 0, 7: 0}
        for match in pp_matches:
            results, seeding = get_new_pool_results(results, match, [5, 6, 7], seeding)

        # H2H GD within the position pool only: B +4, A -1, C -3
        self.assertEqual(results[self.team_b.id]["rank"], 1)
        self.assertEqual(results[self.team_a.id]["rank"], 2)
        self.assertEqual(results[self.team_c.id]["rank"], 3)

    def test_sort_tied_teams_fully_tied_group_keeps_order(self) -> None:
        tied = [
            {"id": self.team_a.id, "GF": 30, "GA": 30},
            {"id": self.team_b.id, "GF": 30, "GA": 30},
        ]
        result = sort_tied_teams(tied, self.tournament.id, self.pool)
        self.assertEqual([t["id"] for t in result], [self.team_a.id, self.team_b.id])


class SwissTieBreakRestartTests(ApiBaseTestCase):
    """Swiss ties must restart at H2H once a criterion separates the group."""

    def setUp(self) -> None:
        super().setUp()
        self.swiss_round = SwissRound.objects.create(
            tournament=self.tournament,
            name="A",
            sequence_number=1,
            num_rounds=4,
            current_round=3,
            initial_seeding={i + 1: self.teams[i].id for i in range(6)},
            results={},
            byes={},
        )
        self.team_a, self.team_b, self.team_c = self.teams[:3]
        self.team_d, self.team_e, self.team_f = self.teams[3:6]

    def _swiss_match(self, team_1: Team, team_2: Team, score_1: int, score_2: int) -> Match:
        return Match.objects.create(
            tournament=self.tournament,
            swiss_round=self.swiss_round,
            team_1=team_1,
            team_2=team_2,
            score_team_1=score_1,
            score_team_2=score_2,
            status=Match.Status.COMPLETED,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )

    def test_restart_uses_head_to_head_after_opp_strength_separates(self) -> None:
        """Cycle A>B>C>A; A faced stronger opponents; then B beat C directly.

        Old behaviour ordered the B/C remainder by goal difference (C ahead);
        WFDF restart puts B ahead because B won the head-to-head.
        """
        # The A/B/C cycle
        self._swiss_match(self.team_a, self.team_b, 15, 10)
        self._swiss_match(self.team_b, self.team_c, 15, 10)
        self._swiss_match(self.team_c, self.team_a, 15, 10)
        # Extra games defining opponent strength: A played D (strong),
        # B played E (weak), C played F (weak).
        self._swiss_match(self.team_a, self.team_d, 15, 10)
        self._swiss_match(self.team_b, self.team_e, 15, 10)
        self._swiss_match(self.team_c, self.team_f, 15, 10)

        all_results = {
            self.team_a.id: {"wins": 2, "draws": 0, "losses": 1, "GF": 40, "GA": 35},
            self.team_b.id: {"wins": 2, "draws": 0, "losses": 1, "GF": 40, "GA": 38},
            # C gets the best goal difference so the old sort would rank C > B
            self.team_c.id: {"wins": 2, "draws": 0, "losses": 1, "GF": 45, "GA": 30},
            self.team_d.id: {"wins": 3, "draws": 0, "losses": 1, "GF": 60, "GA": 40},
            self.team_e.id: {"wins": 0, "draws": 0, "losses": 3, "GF": 20, "GA": 45},
            self.team_f.id: {"wins": 0, "draws": 0, "losses": 3, "GF": 20, "GA": 45},
        }
        tied = [
            {"id": self.team_c.id, **all_results[self.team_c.id]},
            {"id": self.team_b.id, **all_results[self.team_b.id]},
            {"id": self.team_a.id, **all_results[self.team_a.id]},
        ]

        result = sort_swiss_tied_teams(tied, all_results, self.swiss_round)

        self.assertEqual(
            [t["id"] for t in result],
            [self.team_a.id, self.team_b.id, self.team_c.id],
        )

    def test_bye_reranks_with_swiss_tiebreakers(self) -> None:
        """apply_bye must rank with H2H/opp-strength, not raw goal difference."""
        self._swiss_match(self.team_a, self.team_b, 15, 13)

        self.swiss_round.initial_seeding = {
            1: self.team_a.id,
            2: self.team_b.id,
            3: self.team_c.id,
        }
        self.swiss_round.results = {
            self.team_a.id: {"wins": 1, "draws": 0, "losses": 0, "GF": 15, "GA": 13},
            self.team_b.id: {"wins": 1, "draws": 0, "losses": 0, "GF": 25, "GA": 15},
            self.team_c.id: {"wins": 0, "draws": 0, "losses": 0, "GF": 0, "GA": 0},
        }
        self.swiss_round.save()
        self.tournament.current_seeding = {
            "1": self.team_a.id,
            "2": self.team_b.id,
            "3": self.team_c.id,
        }
        self.tournament.save()

        # C's bye makes it 15-0 (GD +15) — best GD of the three, but C has
        # no head-to-head wins and faced nobody, so C must rank last.
        apply_bye(self.swiss_round, self.team_c.id, 2)

        self.swiss_round.refresh_from_db()
        results = {int(k): v for k, v in self.swiss_round.results.items()}
        self.assertEqual(results[self.team_a.id]["rank"], 1)  # beat B head-to-head
        self.assertEqual(results[self.team_b.id]["rank"], 2)
        self.assertEqual(results[self.team_c.id]["rank"], 3)

    def test_recompute_swiss_ranks_prefers_head_to_head_over_gd(self) -> None:
        self._swiss_match(self.team_a, self.team_b, 15, 14)
        results = {
            self.team_a.id: {"wins": 1, "draws": 0, "losses": 0, "GF": 15, "GA": 14},
            self.team_b.id: {"wins": 1, "draws": 0, "losses": 0, "GF": 30, "GA": 14},
        }
        seeding = {1: 0, 2: 0}
        results, seeding = recompute_swiss_ranks(self.swiss_round, results, [1, 2], seeding)
        self.assertEqual(results[self.team_a.id]["rank"], 1)
        self.assertEqual(seeding[1], self.team_a.id)


class BracketNameValidationTests(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def _create(self, name: str) -> int:
        response = self.client.post(
            f"/api/tournament/bracket/{self.tournament.id}",
            {"name": name, "sequence_number": 1},
            content_type="application/json",
        )
        return response.status_code

    def test_valid_bracket_creates_matches(self) -> None:
        self.assertEqual(self._create("1-8"), 200)
        bracket = Bracket.objects.get(tournament=self.tournament)
        self.assertEqual(Match.objects.filter(bracket=bracket).count(), 12)

    def test_non_numeric_name_rejected(self) -> None:
        self.assertEqual(self._create("Top8"), 400)
        self.assertEqual(Bracket.objects.filter(tournament=self.tournament).count(), 0)

    def test_reversed_range_rejected(self) -> None:
        self.assertEqual(self._create("8-1"), 400)

    def test_odd_sized_range_rejected(self) -> None:
        # Odd ranges used to create a bracket silently containing no matches
        self.assertEqual(self._create("1-5"), 400)
        self.assertEqual(Bracket.objects.filter(tournament=self.tournament).count(), 0)

    def test_zero_seed_rejected(self) -> None:
        self.assertEqual(self._create("0-3"), 400)

    def test_validate_bracket_name_unit(self) -> None:
        self.assertTrue(validate_bracket_name("9-16")[0])
        self.assertTrue(validate_bracket_name("5-6")[0])
        self.assertFalse(validate_bracket_name("5-5")[0])
        self.assertFalse(validate_bracket_name("1-8-9")[0])
        self.assertFalse(validate_bracket_name("finals")[0])
