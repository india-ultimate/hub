from __future__ import annotations

from collections.abc import Iterable
from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest.mock import patch

from server.core.models import Team, User
from server.tests.base import ApiBaseTestCase, create_pool
from server.tournament.models import Match, Pool, SwissRound, Tournament

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

REFUSAL = "This tournament is unseeded. Use Redraw to draw a new order."


def reverse_order(team_ids: Iterable[int]) -> list[int]:
    return sorted(team_ids, reverse=True)


class TestUnseededTournament(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def _put_seeded(self, seeded: bool) -> Response:
        return self.client.put(
            f"/api/tournament/{self.tournament.id}/seeded",
            {"seeded": seeded},
            content_type="application/json",
        )

    def _draw(self) -> Response:
        return self.client.post(f"/api/tournament/{self.tournament.id}/draw")

    def _go_live(self) -> None:
        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()

    def _unseed_reversed(self) -> None:
        with patch("server.tournament.utils.draw_order", reverse_order):
            self.assertEqual(self._put_seeded(False).status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()

    def test_default_is_seeded(self) -> None:
        self.assertTrue(self.tournament.seeded)
        response = self.client.get(f"/api/tournament?id={self.tournament.id}")
        self.assertTrue(response.json()["seeded"])

    def test_switch_to_unseeded_draws(self) -> None:
        response = self._put_seeded(False)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(response.json()["seeded"])
        self.tournament.refresh_from_db()
        self.assertEqual(
            sorted(self.tournament.initial_seeding.values()), sorted(t.id for t in self.teams)
        )

    def test_switch_to_unseeded_uses_the_draw(self) -> None:
        self._unseed_reversed()
        expected = {str(i): t for i, t in enumerate(reverse_order(t.id for t in self.teams), 1)}
        self.assertEqual(self.tournament.initial_seeding, expected)
        self.assertEqual(self.tournament.current_seeding, expected)

    def test_redraw_changes_order(self) -> None:
        self._unseed_reversed()
        before = dict(self.tournament.initial_seeding)
        with patch("server.tournament.utils.draw_order", sorted):
            self.assertEqual(self._draw().status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()
        self.assertNotEqual(self.tournament.initial_seeding, before)

    def test_manual_seeding_refused_when_unseeded(self) -> None:
        self._unseed_reversed()
        before = dict(self.tournament.initial_seeding)
        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": {str(i): t.id for i, t in enumerate(self.teams, 1)}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], REFUSAL)
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.initial_seeding, before)

    def test_switch_refused_when_live(self) -> None:
        self._go_live()
        self.assertEqual(self._put_seeded(False).status_code, 400)
        self.tournament.refresh_from_db()
        self.assertTrue(self.tournament.seeded)

    def test_draw_refused_when_live(self) -> None:
        self._unseed_reversed()
        self._go_live()
        before = dict(self.tournament.initial_seeding)
        self.assertEqual(self._draw().status_code, 400)
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.initial_seeding, before)

    def test_non_manager_forbidden(self) -> None:
        other = User.objects.create(username="other@foo.com", email="other@foo.com")
        self.client.force_login(other)
        self.assertEqual(self._put_seeded(False).status_code, 401)
        self.assertEqual(self._draw().status_code, 401)
        self.tournament.refresh_from_db()
        self.assertTrue(self.tournament.seeded)

    def test_unseeded_resyncs_pools_and_swiss_and_redraws_lots(self) -> None:
        create_pool("A", self.tournament, [1, 2, 3, 4])
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [5, 6, 7, 8], "sequence_number": 1, "name": "S"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        old_lots = dict(SwissRound.objects.get().lots)

        self._unseed_reversed()

        draw = {int(k): v for k, v in self.tournament.initial_seeding.items()}
        pool = Pool.objects.get(tournament=self.tournament)
        self.assertEqual(
            {int(k): v for k, v in pool.initial_seeding.items()}, {s: draw[s] for s in (1, 2, 3, 4)}
        )
        swiss = SwissRound.objects.get()
        self.assertEqual(
            {int(k): v for k, v in swiss.initial_seeding.items()},
            {s: draw[s] for s in (5, 6, 7, 8)},
        )
        self.assertEqual(set(swiss.lots), {str(draw[s]) for s in (5, 6, 7, 8)})
        self.assertNotEqual(set(swiss.lots), set(old_lots))

        self.assertEqual(
            self.client.post(f"/api/tournament/start/{self.tournament.id}").status_code, 200
        )
        r1 = Match.objects.filter(swiss_round=swiss, sequence_number=1)
        self.assertEqual(
            {frozenset((m.team_1_id, m.team_2_id)) for m in r1},
            {frozenset((draw[5], draw[8])), frozenset((draw[6], draw[7]))},
        )

    def test_odd_unseeded_round_one_bye_is_last_drawn_seed(self) -> None:
        self.tournament.teams.remove(self.teams[7])
        self._unseed_reversed()
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [1, 2, 3, 4, 5, 6, 7], "sequence_number": 1, "name": "S"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(
            self.client.post(f"/api/tournament/start/{self.tournament.id}").status_code, 200
        )

        draw = {int(k): v for k, v in self.tournament.initial_seeding.items()}
        bye_team = draw[7]
        swiss = SwissRound.objects.get()
        in_r1 = {
            t
            for m in Match.objects.filter(swiss_round=swiss, sequence_number=1)
            for t in (m.team_1_id, m.team_2_id)
        }
        self.assertNotIn(bye_team, in_r1)
        self.assertEqual(len(in_r1), 6)
        self.assertEqual(swiss.results[str(bye_team)]["wins"], 1)

    def test_team_added_redraws_when_unseeded(self) -> None:
        self.tournament.teams.remove(self.teams[7])
        self._unseed_reversed()
        with patch("server.tournament.models.draw_order", reverse_order):
            self.tournament.teams.add(self.teams[7])
        self.tournament.refresh_from_db()
        expected = {str(i): t for i, t in enumerate(reverse_order(t.id for t in self.teams), 1)}
        self.assertEqual(self.tournament.initial_seeding, expected)

    def test_team_added_resyncs_stages_and_the_event_can_start(self) -> None:
        self.tournament.teams.remove(self.teams[7])
        self.assertEqual(self._put_seeded(False).status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()
        create_pool("A", self.tournament, [1, 2, 3])
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [4, 5, 6, 7], "sequence_number": 1, "name": "S"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        team_admin = User.objects.create(username="ta@foo.com", email="ta@foo.com")
        self.teams[7].admins.add(team_admin)
        self.client.force_login(team_admin)
        with patch("server.api.is_today_in_between_dates", return_value=True):
            response = self.client.put(
                f"/api/tournament/{self.tournament.id}/register-team",
                {"team_id": self.teams[7].id},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)
        self.client.force_login(self.user)

        self.tournament.refresh_from_db()
        draw = {int(k): v for k, v in self.tournament.initial_seeding.items()}
        self.assertEqual(sorted(draw.values()), sorted(t.id for t in self.teams))
        pool = Pool.objects.get()
        self.assertEqual(
            {int(k): v for k, v in pool.initial_seeding.items()}, {s: draw[s] for s in (1, 2, 3)}
        )
        self.assertEqual(set(pool.results), {str(draw[s]) for s in (1, 2, 3)})
        swiss = SwissRound.objects.get()
        self.assertEqual(
            {int(k): v for k, v in swiss.initial_seeding.items()},
            {s: draw[s] for s in (4, 5, 6, 7)},
        )
        self.assertEqual(set(swiss.lots), {str(draw[s]) for s in (4, 5, 6, 7)})

        self.assertEqual(
            self.client.post(f"/api/tournament/start/{self.tournament.id}").status_code, 200
        )
        match = Match.objects.filter(pool=pool).order_by("id")[0]
        self.assertIn(str(match.team_1_id), pool.results)
        response = self.client.post(
            f"/api/match/{match.id}/score",
            {"team_1_score": 15, "team_2_score": 10},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)
        pool.refresh_from_db()
        self.assertEqual(pool.results[str(match.team_1_id)]["wins"], 1)
        self.assertEqual(pool.results[str(match.team_2_id)]["losses"], 1)

    def _stage_pool_and_swiss(self) -> None:
        create_pool("A", self.tournament, [1, 2, 3])
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [4, 5, 6, 7], "sequence_number": 1, "name": "S"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def _assert_stages_follow_the_draw(self, teams: list[Team]) -> None:
        self.tournament.refresh_from_db()
        draw = {int(k): v for k, v in self.tournament.initial_seeding.items()}
        self.assertEqual(sorted(draw.values()), sorted(t.id for t in teams))
        self.assertEqual(len(draw), len(teams))
        pool = Pool.objects.get()
        self.assertEqual(
            {int(k): v for k, v in pool.initial_seeding.items()}, {s: draw[s] for s in (1, 2, 3)}
        )
        self.assertEqual(set(pool.results), {str(draw[s]) for s in (1, 2, 3)})
        swiss = SwissRound.objects.get()
        self.assertEqual(
            {int(k): v for k, v in swiss.initial_seeding.items()},
            {s: draw[s] for s in (4, 5, 6, 7)},
        )
        self.assertEqual(set(swiss.results), {str(draw[s]) for s in (4, 5, 6, 7)})
        self.assertEqual(set(swiss.lots), set(swiss.results))

    def test_adding_a_team_with_the_real_draw_is_a_permutation(self) -> None:
        self.tournament.teams.remove(self.teams[7])
        self.assertEqual(self._put_seeded(False).status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()
        self._stage_pool_and_swiss()

        self.tournament.teams.add(self.teams[7])

        self._assert_stages_follow_the_draw(self.teams)

    def test_removing_a_team_with_the_real_draw_is_a_permutation(self) -> None:
        self.assertEqual(self._put_seeded(False).status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()
        self._stage_pool_and_swiss()

        self.tournament.teams.remove(self.teams[7])

        self._assert_stages_follow_the_draw(self.teams[:7])

    def test_team_added_no_redraw_when_live(self) -> None:
        self.tournament.teams.remove(self.teams[7])
        self._unseed_reversed()
        self._go_live()
        with patch("server.tournament.models.draw_order") as draw:
            self.tournament.teams.add(self.teams[7])
        draw.assert_not_called()

    def test_switch_back_to_seeded_keeps_order(self) -> None:
        self._unseed_reversed()
        before = dict(self.tournament.initial_seeding)
        response = self._put_seeded(True)
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.tournament.refresh_from_db()
        self.assertTrue(self.tournament.seeded)
        self.assertEqual(self.tournament.initial_seeding, before)

    def _stage_and_drop_a_team(self) -> None:
        create_pool("A", self.tournament, [1, 2, 3, 4])
        response = self.client.post(
            f"/api/tournament/swiss-round/{self.tournament.id}",
            {"num_rounds": 3, "seeding": [5, 6, 7, 8], "sequence_number": 1, "name": "S"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(self._put_seeded(False).status_code, HTTPStatus.OK)
        self.team_admin = User.objects.create(username="ta@foo.com", email="ta@foo.com")
        self.teams[7].admins.add(self.team_admin)
        self.client.force_login(self.team_admin)
        with patch("server.api.is_today_in_between_dates", return_value=True):
            response = self.client.put(
                f"/api/tournament/{self.tournament.id}/deregister-team",
                {"team_id": self.teams[7].id},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, HTTPStatus.OK, response.content)
        self.client.force_login(self.user)
        self.tournament.refresh_from_db()

    def test_dropping_a_team_does_not_crash_and_leaves_a_permutation(self) -> None:
        self._stage_and_drop_a_team()
        self.assertEqual(
            sorted(self.tournament.initial_seeding.values()),
            sorted(t.id for t in self.teams[:7]),
        )
        self.assertEqual(self.tournament.initial_seeding, self.tournament.current_seeding)

    def test_redraw_refused_with_a_clear_message_when_a_stage_uses_a_missing_seed(self) -> None:
        self._stage_and_drop_a_team()
        before = dict(self.tournament.initial_seeding)
        response = self._draw()
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            response.json()["message"],
            "A pool or Swiss group uses seed 8, but the tournament has 7 teams. "
            "Edit or delete it, then try again.",
        )
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.initial_seeding, before)

    def test_manual_update_refused_the_same_way_when_seeded(self) -> None:
        self._stage_and_drop_a_team()
        self.tournament.seeded = True
        self.tournament.save()
        response = self.client.put(
            f"/api/tournament/update/{self.tournament.id}",
            {"seeding": {str(i): t.id for i, t in enumerate(self.teams[:7], 1)}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("uses seed 8, but the tournament has 7 teams", response.json()["message"])

    def test_failed_draw_rolls_back_the_switch(self) -> None:
        with patch(
            "server.tournament.utils.draw_tournament_seeding",
            return_value=(False, {"message": "nope"}),
        ):
            response = self._put_seeded(False)
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json()["message"], "nope")
        self.tournament.refresh_from_db()
        self.assertTrue(self.tournament.seeded)
