import json

from server.core.models import User
from server.tests.base import ApiBaseTestCase, create_event
from server.tournament.models import Tournament, TournamentField
from server.tournament.utils import can_access_tournament_agent, can_manage_tournament


class TournamentDirectorTests(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.director = User.objects.create(
            username="director@foo.com", email="director@foo.com", first_name="Di", last_name="Rect"
        )
        self.outsider = User.objects.create(
            username="outsider@foo.com",
            email="outsider@foo.com",
            first_name="Out",
            last_name="Sider",
        )
        other_event = create_event("Other Sectionals")
        self.other_tournament = Tournament.objects.create(event=other_event)
        self.tournament.directors.add(self.director)

    def test_helper_staff_and_assigned_director(self) -> None:
        self.assertFalse(can_manage_tournament(self.outsider, self.tournament))
        self.assertTrue(can_manage_tournament(self.director, self.tournament))
        self.assertFalse(can_manage_tournament(self.director, self.other_tournament))
        self.user.is_staff = True
        self.assertTrue(can_manage_tournament(self.user, self.tournament))
        self.assertTrue(can_manage_tournament(self.user, self.other_tournament))
        self.assertTrue(can_access_tournament_agent(self.director))
        self.assertFalse(can_access_tournament_agent(self.outsider))

    def test_me_exposes_directed_tournament_ids(self) -> None:
        self.client.force_login(self.director)
        response = self.client.get("/api/me")
        self.assertEqual(200, response.status_code)
        self.assertEqual([self.tournament.id], response.json()["directed_tournament_ids"])

    def test_me_access_director_flag_is_per_tournament(self) -> None:
        self.client.force_login(self.director)
        assigned = self.client.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, assigned.status_code)
        self.assertTrue(assigned.json()["is_tournament_director"])

        other = self.client.get(
            f"/api/me/access?tournament_slug={self.other_tournament.event.slug}"
        )
        self.assertEqual(200, other.status_code)
        self.assertFalse(other.json()["is_tournament_director"])

    def test_director_can_create_field_only_on_assigned_tournament(self) -> None:
        self.client.force_login(self.director)
        payload = {"name": "Field D", "is_broadcasted": False, "address": None}
        ok = self.client.post(
            f"/api/tournament/{self.tournament.id}/field",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(200, ok.status_code)
        self.assertTrue(
            TournamentField.objects.filter(tournament=self.tournament, name="Field D").exists()
        )

        denied = self.client.post(
            f"/api/tournament/{self.other_tournament.id}/field",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(401, denied.status_code)

    def test_outsider_cannot_manage(self) -> None:
        self.client.force_login(self.outsider)
        response = self.client.post(
            f"/api/tournament/{self.tournament.id}/field",
            data=json.dumps({"name": "Nope", "is_broadcasted": False, "address": None}),
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

    def test_director_cannot_create_or_delete_tournament(self) -> None:
        self.client.force_login(self.director)
        create = self.client.post(
            "/api/tournaments",
            data={
                "tournament_details": json.dumps(
                    {
                        "title": "Director Cup",
                        "start_date": "2026-09-01",
                        "end_date": "2026-09-02",
                        "team_registration_start_date": "2026-08-01",
                        "team_registration_end_date": "2026-08-10",
                        "player_registration_start_date": "2026-08-11",
                        "player_registration_end_date": "2026-08-20",
                        "team_partial_registration_end_date": "2026-08-05",
                        "team_late_penalty_end_date": "2026-08-12",
                        "player_late_penalty_end_date": "2026-08-22",
                        "location": "City",
                        "type": "MXD",
                        "team_fee": 0,
                        "player_fee": 0,
                        "partial_team_fee": 0,
                        "team_late_penalty": 0,
                        "player_late_penalty": 0,
                    }
                )
            },
        )
        self.assertEqual(401, create.status_code)

        delete = self.client.delete(f"/api/tournament/delete/{self.tournament.id}")
        self.assertEqual(401, delete.status_code)
        self.assertTrue(Tournament.objects.filter(id=self.tournament.id).exists())

    def test_staff_appoints_and_director_cannot(self) -> None:
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        add = self.client.post(
            f"/api/tournament/{self.other_tournament.id}/directors",
            data=json.dumps({"user_id": self.outsider.id}),
            content_type="application/json",
        )
        self.assertEqual(200, add.status_code)
        self.assertTrue(self.other_tournament.directors.filter(pk=self.outsider.id).exists())

        self.client.force_login(self.director)
        denied = self.client.post(
            f"/api/tournament/{self.tournament.id}/directors",
            data=json.dumps({"user_id": self.outsider.id}),
            content_type="application/json",
        )
        self.assertEqual(401, denied.status_code)

    def test_revoke_director_blocks_management(self) -> None:
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        remove = self.client.delete(
            f"/api/tournament/{self.tournament.id}/directors/{self.director.id}"
        )
        self.assertEqual(200, remove.status_code)

        self.client.force_login(self.director)
        response = self.client.post(
            f"/api/tournament/{self.tournament.id}/field",
            data=json.dumps({"name": "Gone", "is_broadcasted": False, "address": None}),
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

    def test_director_can_use_agent_only_on_assigned_tournament(self) -> None:
        self.client.force_login(self.director)
        models = self.client.get("/api/tournament-agent/models")
        self.assertEqual(200, models.status_code)

        history = self.client.get(
            f"/api/tournament-agent/history?tournament_id={self.tournament.id}"
        )
        self.assertEqual(200, history.status_code)

        spoof = self.client.get(
            f"/api/tournament-agent/history?tournament_id={self.other_tournament.id}"
        )
        self.assertEqual(401, spoof.status_code)

        self.client.force_login(self.outsider)
        self.assertEqual(401, self.client.get("/api/tournament-agent/models").status_code)
