import json

from server.core.models import Player, Team, User
from server.tests.base import TOURNAMENT_DETAILS, ApiBaseTestCase, create_event
from server.tournament.models import Registration, Tournament, TournamentField
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

    def test_director_can_update_and_delete_field_on_assigned_tournament(self) -> None:
        self.client.force_login(self.director)
        field = TournamentField.objects.create(tournament=self.tournament, name="Field D")
        updated = self.client.put(
            f"/api/tournament/field/{field.id}",
            data=json.dumps(
                {
                    "name": "Field Main",
                    "is_broadcasted": True,
                    "tournament_id": self.tournament.id,
                    "address": "KG Farms",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(200, updated.status_code)
        field.refresh_from_db()
        self.assertEqual(field.name, "Field Main")
        self.assertTrue(field.is_broadcasted)

        deleted = self.client.delete(f"/api/tournament/field/{field.id}")
        self.assertEqual(200, deleted.status_code)
        self.assertFalse(TournamentField.objects.filter(id=field.id).exists())

        other_field = TournamentField.objects.create(tournament=self.other_tournament, name="Other")
        denied = self.client.put(
            f"/api/tournament/field/{other_field.id}",
            data=json.dumps(
                {
                    "name": "Hijack",
                    "is_broadcasted": False,
                    "tournament_id": self.other_tournament.id,
                    "address": None,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(401, denied.status_code)
        denied_del = self.client.delete(f"/api/tournament/field/{other_field.id}")
        self.assertEqual(401, denied_del.status_code)
        self.assertTrue(TournamentField.objects.filter(id=other_field.id).exists())

    def test_delete_field_refused_when_matches_assigned(self) -> None:
        from server.tournament.models import Match

        self.client.force_login(self.director)
        field = TournamentField.objects.create(tournament=self.tournament, name="Busy")
        Match.objects.create(
            tournament=self.tournament,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            field=field,
        )
        response = self.client.delete(f"/api/tournament/field/{field.id}")
        self.assertEqual(400, response.status_code)
        self.assertIn("match", response.json()["message"].lower())
        self.assertTrue(TournamentField.objects.filter(id=field.id).exists())

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
            data={"tournament_details": json.dumps(TOURNAMENT_DETAILS)},
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


class RegistrationListAccessTests(ApiBaseTestCase):
    """Both lists carry players' email, phone, DOB, guardian and college ID."""

    def setUp(self) -> None:
        super().setUp()
        self.director = User.objects.create(username="director@foo.com", email="director@foo.com")
        self.outsider = User.objects.create(username="outsider@foo.com", email="outsider@foo.com")
        self.staff = User.objects.create(
            username="staff@foo.com", email="staff@foo.com", is_staff=True
        )
        self.tournament.directors.add(self.director)
        Registration.objects.create(event=self.event, team=self.teams[0], player=self.player)
        self.urls = [
            f"/api/registrations/tournament/{self.tournament.id}",
            f"/api/registrations/{self.event.id}",
        ]

    def test_signed_out_is_401(self) -> None:
        for url in self.urls:
            self.assertEqual(401, self.client.get(url).status_code, url)

    def test_a_player_who_doesnt_run_the_tournament_is_403(self) -> None:
        for viewer in (self.outsider, self.user):  # self.user is the registered player
            self.client.force_login(viewer)
            for url in self.urls:
                response = self.client.get(url)
                self.assertEqual(403, response.status_code, url)
                self.assertNotIn(self.username, response.content.decode())
                self.assertIn("message", response.json())

    def test_a_director_of_another_tournament_is_403(self) -> None:
        other = User.objects.create(username="other@foo.com", email="other@foo.com")
        Tournament.objects.create(event=create_event("Other Sectionals")).directors.add(other)
        self.client.force_login(other)
        for url in self.urls:
            self.assertEqual(403, self.client.get(url).status_code, url)

    def test_staff_and_the_tournaments_director_see_the_details(self) -> None:
        for viewer in (self.staff, self.director):
            self.client.force_login(viewer)
            players = self.client.get(self.urls[0])
            self.assertEqual(200, players.status_code)
            [player] = [r["player"] for r in players.json()]
            # What ValidateRoster reads.
            for field in (
                "id",
                "full_name",
                "date_of_birth",
                "accreditation",
                "subscription",
                "college_id",
                "vaccination",
                "match_up",
                "ultimate_central_id",
            ):
                self.assertIn(field, player)
            self.assertEqual("1990-01-01", player["date_of_birth"])
            uc = self.client.get(self.urls[1])
            self.assertEqual(200, uc.status_code)
            self.assertIn(self.username, {r["person"]["email"] for r in uc.json()})

    def test_an_unknown_tournament_is_404_not_500(self) -> None:
        self.client.force_login(self.staff)
        self.assertEqual(404, self.client.get("/api/registrations/tournament/999999").status_code)

    def test_a_team_admin_sees_only_their_own_teams_registrations(self) -> None:
        captain = User.objects.create(username="captain@foo.com", email="captain@foo.com")
        self.teams[1].admins.add(captain)
        other = User.objects.create(username="other-player@foo.com", email="other-player@foo.com")
        mine = Player.objects.create(user=other, date_of_birth="1995-05-05")
        Registration.objects.create(event=self.event, team=self.teams[1], player=mine)

        self.client.force_login(captain)
        response = self.client.get(self.urls[0])

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([mine.id], [r["player"]["id"] for r in response.json()])
        self.assertNotIn(self.username, response.content.decode())
        self.assertNotIn("1990-01-01", response.content.decode())
        # The UC list is still staff and directors only.
        self.assertEqual(403, self.client.get(self.urls[1]).status_code)

        for viewer in (self.staff, self.director):
            self.client.force_login(viewer)
            players = {r["player"]["id"] for r in self.client.get(self.urls[0]).json()}
            self.assertEqual({self.player.id, mine.id}, players)

    def test_an_admin_of_a_team_outside_the_tournament_is_403(self) -> None:
        captain = User.objects.create(username="captain@foo.com", email="captain@foo.com")
        Team.objects.create(name="Elsewhere").admins.add(captain)
        self.client.force_login(captain)
        self.assertEqual(403, self.client.get(self.urls[0]).status_code)
