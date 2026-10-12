"""A team admin changing who else administers the team (ticket #362)."""

import json
from typing import cast

from django.test import TestCase

from server.core.models import Team, User


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
