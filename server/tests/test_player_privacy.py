"""Responses that carry players never show a stranger their contact details.

Each test seeds a player with distinctive email, phone and date of birth,
and searches whole response bodies for them.
"""

import datetime

from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, Team, User
from server.registration.models import RosterEntry
from server.season.models import Season
from server.tests.base import create_event

EMAIL = "hidden.secret@example.org"
PHONE = "9123498765"
DOB = datetime.date(2011, 7, 19)


class PlayerPrivacyTestCase(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create(
            username=EMAIL, email=EMAIL, phone=PHONE, first_name="Secret", last_name="Keeper"
        )
        self.player = Player.objects.create(user=self.owner, date_of_birth=DOB, city="Pune")
        self.guardian = User.objects.create(username="parent@x.com", email="parent@x.com")
        Guardianship.objects.create(user=self.guardian, player=self.player, relation="MO")
        self.staff = User.objects.create(username="staff@x.com", email="staff@x.com", is_staff=True)
        self.stranger = User.objects.create(username="stranger@x.com", email="stranger@x.com")

    def assert_no_secrets(self, response: object, viewer: User) -> None:
        body = response.content.decode()  # type: ignore[attr-defined]
        for secret in (EMAIL, PHONE, DOB.isoformat()):
            self.assertNotIn(secret, body, f"{secret} shown to {viewer.username}")


class TestUnderMinAgeUsesTheSeasonEnd(PlayerPrivacyTestCase):
    def test_it_is_the_age_at_the_season_end_like_the_subscription_page_checks(self) -> None:
        team = Team.objects.create(name="Roster Team", slug="roster-team")
        captain = User.objects.create(username="captain@x.com", email="captain@x.com")
        team.admins.add(captain)
        today = now().date()
        # Eleven and ten months old: twelve by the time the season ends.
        almost = Player.objects.create(
            user=User.objects.create(username="almost@x.com"),
            date_of_birth=today - datetime.timedelta(days=365 * 11 + 300),
            city="Pune",
        )
        RosterEntry.objects.create(event=create_event("Nationals"), team=team, player=almost)
        Season.objects.create(
            name="Now", start_date=today, end_date=today + datetime.timedelta(days=120)
        )
        self.client.force_login(captain)
        self.assertFalse(self.client.get(f"/api/players/{almost.id}").json()["under_min_age"])
        young = Player.objects.create(
            user=User.objects.create(username="young@x.com"),
            date_of_birth=today - datetime.timedelta(days=365 * 10),
            city="Pune",
        )
        RosterEntry.objects.create(event=create_event("Nationals"), team=team, player=young)
        self.assertTrue(self.client.get(f"/api/players/{young.id}").json()["under_min_age"])


class TestPlayerDetail(PlayerPrivacyTestCase):
    def url(self) -> str:
        return f"/api/players/{self.player.id}"

    def test_the_player_their_guardian_and_staff_see_everything(self) -> None:
        for viewer in (self.owner, self.guardian, self.staff):
            self.client.force_login(viewer)
            response = self.client.get(self.url())
            self.assertEqual(200, response.status_code, viewer.username)
            data = response.json()
            self.assertEqual((EMAIL, PHONE), (data["email"], data["phone"]))
            self.assertEqual(DOB.isoformat(), data["date_of_birth"])

    def test_a_stranger_is_refused(self) -> None:
        self.client.force_login(self.stranger)
        response = self.client.get(self.url())
        self.assertEqual(403, response.status_code)
        self.assert_no_secrets(response, self.stranger)

    def test_an_admin_whose_roster_holds_them_sees_only_what_paying_needs(self) -> None:
        # The registration page sends them to the group subscription page,
        # which loads each player on the roster still needing a subscription.
        team = Team.objects.create(name="Roster Team", slug="roster-team")
        captain = User.objects.create(username="captain@x.com", email="captain@x.com")
        team.admins.add(captain)
        RosterEntry.objects.create(event=create_event("Nationals"), team=team, player=self.player)

        self.client.force_login(captain)
        response = self.client.get(self.url())

        self.assertEqual(200, response.status_code, response.content)
        self.assert_no_secrets(response, captain)
        self.assertEqual(
            {"id", "full_name", "is_minor", "under_min_age", "iu_id", "teams", "subscription"},
            set(response.json()),
        )
        self.assertTrue(response.json()["is_minor"])

    def test_an_admin_sees_the_age_flag_and_iu_id_the_subscription_page_needs(self) -> None:
        team = Team.objects.create(name="Roster Team", slug="roster-team")
        captain = User.objects.create(username="captain@x.com", email="captain@x.com")
        team.admins.add(captain)
        child = User.objects.create(username="kid@x.com", first_name="Kid", last_name="Under")
        young = Player.objects.create(
            user=child,
            date_of_birth=now().date() - datetime.timedelta(days=365 * 10),
            iu_id="IU-77",
        )
        for player in (young, self.player):
            RosterEntry.objects.create(event=create_event("Nationals"), team=team, player=player)

        self.client.force_login(captain)
        slim = self.client.get(f"/api/players/{young.id}").json()
        self.assertEqual((True, "IU-77"), (slim["under_min_age"], slim["iu_id"]))
        self.assertNotIn("date_of_birth", slim)
        self.assertFalse(self.client.get(self.url()).json()["under_min_age"])

    def test_an_admin_of_an_unrelated_team_is_refused(self) -> None:
        team = Team.objects.create(name="Other Team", slug="other-team")
        team.admins.add(self.stranger)
        self.client.force_login(self.stranger)
        self.assertEqual(403, self.client.get(self.url()).status_code)


class TestUserSearch(PlayerPrivacyTestCase):
    def search(self, text: str) -> list[dict[str, object]]:
        response = self.client.get("/api/users/search", {"text": text})
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def test_a_stranger_finds_a_name_with_its_email_masked(self) -> None:
        self.client.force_login(self.stranger)
        response = self.client.get("/api/users/search", {"text": "secret k"})
        self.assert_no_secrets(response, self.stranger)
        [found] = response.json()
        self.assertEqual(
            {
                "id": self.owner.id,
                "full_name": "Secret Keeper",
                "username": "hixxxxxxxxxet@example.org",
            },
            found,
        )
        # Searching by address still finds them, still masked.
        self.assertEqual([self.owner.id], [u["id"] for u in self.search("hidden.secret")])

    def test_staff_see_the_address(self) -> None:
        self.client.force_login(self.staff)
        self.assertEqual([EMAIL], [u["username"] for u in self.search("secret k")])

    def test_under_three_characters_finds_no_one(self) -> None:
        self.client.force_login(self.stranger)
        for text in ("", "  ", "se", " x "):
            self.assertEqual([], self.search(text), text)

    def test_at_most_twenty_are_returned(self) -> None:
        for i in range(25):
            User.objects.create(username=f"many{i}@x.com", email=f"many{i}@x.com")
        self.client.force_login(self.stranger)
        self.assertEqual(20, len(self.search("many")))


class TestPlayerList(PlayerPrivacyTestCase):
    def test_only_staff_can_list_every_player(self) -> None:
        # Only the staff page reads it.
        for viewer in (self.stranger, self.owner, self.guardian):
            self.client.force_login(viewer)
            for url in ("/api/players", "/api/players?full_schema=1"):
                response = self.client.get(url)
                self.assertEqual(403, response.status_code, url)
                self.assert_no_secrets(response, viewer)

        self.client.force_login(self.staff)
        [player] = self.client.get("/api/players?full_schema=1").json()
        self.assertEqual((EMAIL, PHONE), (player["email"], player["phone"]))
