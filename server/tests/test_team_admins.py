"""A team admin changing who else administers the team (ticket #362)."""

import json
from typing import cast

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from server.core.models import Team, User
from server.schema import TeamSchema


def user(name: str) -> User:
    return User.objects.create(username=f"{name}@x.com", email=f"{name}@x.com", first_name=name)


class TestTeamAdmins(TestCase):
    def setUp(self) -> None:
        self.me, self.meshach, self.arpita = user("me"), user("meshach"), user("arpita")
        self.team = Team.objects.create(
            name="No Fly Zone", category="Club", state_ut="TN", city="Coimbatore"
        )
        self.team.admins.add(self.me, self.meshach, self.arpita)
        self.client.force_login(self.me)

    def edit(self, **details: object) -> int:
        body = {"team_details": json.dumps({"id": str(self.team.id), **details})}
        self.response = self.client.post("/api/teams/edit", body)
        return self.response.status_code

    def admins(self) -> set[User]:
        return set(self.team.admins.all())

    def test_removing_admins_removes_them(self) -> None:
        # The form sends the admins to keep; the server only ever added.
        self.assertEqual(200, self.edit(admin_ids=[self.me.id]))
        self.assertEqual({self.me}, self.admins())

    def test_adding_an_admin_still_works(self) -> None:
        new = user("new")
        ids = [self.me.id, self.meshach.id, self.arpita.id, new.id]
        self.assertEqual(200, self.edit(admin_ids=ids))
        self.assertEqual({self.me, self.meshach, self.arpita, new}, self.admins())

    def test_an_unknown_admin_changes_nothing(self) -> None:
        # Or a typo'd id would quietly drop everyone else.
        self.assertEqual(400, self.edit(admin_ids=[self.me.id, 999999]))
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_leaving_admins_out_keeps_them(self) -> None:
        self.assertEqual(200, self.edit(city="Chennai"))
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_an_admin_cant_remove_themselves(self) -> None:
        # Or a slip in the admins box locks them out of their own team.
        self.assertEqual(400, self.edit(admin_ids=[self.meshach.id]))
        self.assertIn("yourself", self.response.json()["message"])
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_an_id_that_isnt_a_number_is_refused(self) -> None:
        self.assertEqual(422, self.edit(admin_ids=[self.me.id, "abc"]))
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_a_non_admin_cant_change_admins(self) -> None:
        outsider = user("outsider")
        self.client.force_login(outsider)
        self.assertEqual(400, self.edit(admin_ids=[outsider.id]))
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_removing_everyone_is_refused(self) -> None:
        self.assertEqual(400, self.edit(admin_ids=[]))
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_a_state_that_isnt_one_is_refused_and_nothing_is_saved(self) -> None:
        # Too long for the column: it used to save the other fields, then 500.
        self.assertEqual(400, self.edit(state_ut="TOOLONG", city="Chennai", category="School"))
        self.assertIn("state", self.response.json()["message"].lower())
        self.team.refresh_from_db()
        self.assertEqual(
            ("TN", "Coimbatore", "Club"), (self.team.state_ut, self.team.city, self.team.category)
        )
        self.assertEqual({self.me, self.meshach, self.arpita}, self.admins())

    def test_a_city_too_long_for_the_column_is_refused_and_nothing_is_saved(self) -> None:
        too_long = "C" * (cast(int, Team._meta.get_field("city").max_length) + 1)
        self.assertEqual(400, self.edit(city=too_long, category="School"))
        self.assertIn("city", self.response.json()["message"].lower())
        self.team.refresh_from_db()
        self.assertEqual(("Coimbatore", "Club"), (self.team.city, self.team.category))


class TestAdminsArePrivate(TestCase):
    """Who administers a team is public; their email addresses are not."""

    def setUp(self) -> None:
        self.admin = user("admin")
        self.team = Team.objects.create(
            name="No Fly Zone", slug="no-fly-zone", category="Club", state_ut="TN", city="Kovai"
        )
        self.team.admins.add(self.admin)

    def assert_no_addresses(self, content: bytes) -> None:
        self.assertNotIn(b"admin@x.com", content)

    def test_anyone_sees_admins_names_but_not_their_addresses(self) -> None:
        for viewer in (None, user("other")):
            if viewer is not None:
                self.client.force_login(viewer)
            for url in ("/api/teams", "/api/team/no-fly-zone", "/api/teams/search?text=fly"):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)
                self.assert_no_addresses(response.content)
            team = self.client.get("/api/team/no-fly-zone").json()
            self.assertEqual(team["admins"], [{"id": self.admin.id, "full_name": "admin"}])

    def test_every_schema_that_embeds_a_team_sends_only_id_and_name(self) -> None:
        # Matches, match events and UC registrations embed TeamSchema too.
        admins = TeamSchema.from_orm(self.team).dict()["admins"]
        self.assertEqual(admins, [{"id": self.admin.id, "full_name": "admin"}])

    def test_the_admin_can_still_edit_the_team_and_its_admins(self) -> None:
        self.client.force_login(self.admin)
        other = user("other")
        body = {
            "team_details": json.dumps(
                {"id": str(self.team.id), "admin_ids": [self.admin.id, other.id]}
            )
        }
        response = self.client.post("/api/teams/edit", body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(a["id"] for a in response.json()["admins"]), sorted([self.admin.id, other.id])
        )
        self.assert_no_addresses(response.content)

    def test_listing_teams_takes_the_same_queries_however_many(self) -> None:
        def count(url: str) -> int:
            with CaptureQueriesContext(connection) as queries:
                self.assertEqual(200, self.client.get(url).status_code)
            return len(queries)

        urls = ("/api/teams", "/api/teams/search?text=zone")
        before = [count(url) for url in urls]
        for i in range(3):
            team = Team.objects.create(name=f"Zone {i}", slug=f"zone-{i}", category="Club")
            team.admins.add(user(f"admin{i}"))
        self.assertEqual(before, [count(url) for url in urls])


class TestTeamRename(TestCase):
    def setUp(self) -> None:
        self.me = user("me")
        self.team = Team.objects.create(
            name="No Fly Zone", slug="no-fly-zone", category="Club", state_ut="TN", city="Chennai"
        )
        self.team.admins.add(self.me)
        self.client.force_login(self.me)

    def rename(self, name: str) -> str | None:
        body = {"id": str(self.team.id), "name": name}
        response = self.client.put("/api/teams/edit-name", body, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.team.refresh_from_db()
        return self.team.slug

    def test_a_trivial_rename_keeps_the_slug(self) -> None:
        self.assertEqual("no-fly-zone", self.rename("No Fly Zone!"))

    def test_a_taken_slug_gets_one_number(self) -> None:
        Team.objects.create(name="Other", slug="flyers", category="Club")
        Team.objects.create(name="Other 2", slug="flyers-1", category="Club")
        self.assertEqual("flyers-2", self.rename("Flyers"))

    def test_a_numbered_slug_is_kept_when_still_right(self) -> None:
        Team.objects.create(name="Other", slug="flyers", category="Club")
        self.team.slug = "flyers-1"
        self.team.save()
        self.assertEqual("flyers-1", self.rename("Flyers"))
