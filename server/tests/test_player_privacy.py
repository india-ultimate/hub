"""Responses that carry players never show a stranger their contact details.

Each test seeds a player with distinctive email, phone and date of birth,
and searches whole response bodies for them.
"""

import datetime
from typing import Any
from unittest.mock import patch

from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, Team, UCPerson, User
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

    def test_staff_see_the_address(self) -> None:
        self.client.force_login(self.staff)
        self.assertEqual([EMAIL], [u["username"] for u in self.search("secret k")])
        self.assertEqual([EMAIL], [u["username"] for u in self.search("hidden.sec")])

    def test_a_stranger_cannot_find_an_address_by_its_characters(self) -> None:
        self.client.force_login(self.stranger)
        for text in ("hid", "hidden.sec", "example.org", EMAIL[:-1]):
            self.assertEqual([], self.search(text), text)

    def test_a_stranger_finds_someone_by_their_full_address(self) -> None:
        self.client.force_login(self.stranger)
        for text in (EMAIL, EMAIL.upper(), f" {EMAIL} "):
            self.assertEqual([self.owner.id], [u["id"] for u in self.search(text)], text)

    def test_under_three_characters_finds_no_one(self) -> None:
        self.client.force_login(self.stranger)
        for text in ("", "  ", "se", " x "):
            self.assertEqual([], self.search(text), text)

    def test_at_most_twenty_are_returned(self) -> None:
        for i in range(25):
            User.objects.create(username=f"m{i}@x.com", first_name="Many", last_name=str(i))
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


class TestPlayerSearchByEmail(PlayerPrivacyTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.team = Team.objects.create(name="Home", slug="home")
        self.event = create_event("Open")

    def found(self, viewer: User, text: str) -> list[int]:
        self.client.force_login(viewer)
        urls = (
            "/api/players/search",
            f"/api/tournament/{self.event.slug}/team/{self.team.slug}/players/search",
        )
        results = []
        for url in urls:
            response = self.client.get(url, {"text": text})
            self.assertEqual(200, response.status_code, response.content)
            results.append([p["id"] for p in response.json()["items"]])
        self.assertEqual(results[0], results[1], text)
        return results[0]

    def test_a_stranger_cannot_find_a_player_by_email(self) -> None:
        for text in ("hid", "hidden.sec", "example.org", EMAIL[:-1]):
            self.assertEqual([], self.found(self.stranger, text), text)

    def test_the_full_address_finds_them(self) -> None:
        for text in (EMAIL, EMAIL.upper()):
            self.assertEqual([self.player.id], self.found(self.stranger, text), text)

    def test_a_name_finds_them(self) -> None:
        self.assertEqual([self.player.id], self.found(self.stranger, "secret k"))

    def test_staff_can_search_by_email(self) -> None:
        self.assertEqual([self.player.id], self.found(self.staff, "hidden.sec"))

    def test_a_stranger_needs_three_characters_and_gets_at_most_a_page(self) -> None:
        self.assertEqual([], self.found(self.stranger, "se"))
        for i in range(25):
            u = User.objects.create(username=f"m{i}@x.com", first_name="Many", last_name=str(i))
            Player.objects.create(user=u, date_of_birth=DOB, city="Pune")
        self.assertEqual(5, len(self.found(self.stranger, "many")))
        response = self.client.get("/api/players/search", {"text": "many", "page": "5"})
        self.assertEqual([], response.json()["items"])


class TestPlayersInOtherResponses(PlayerPrivacyTestCase):
    def test_player_search_masks_the_email(self) -> None:
        # The service request picker shows it to tell people apart.
        self.client.force_login(self.stranger)
        response = self.client.get("/api/players/search?text=secret")
        self.assert_no_secrets(response, self.stranger)
        [found] = response.json()["items"]
        self.assertEqual("hixxxxxxxxxet@example.org", found["email"])

    def test_matches_name_their_players_and_nothing_more(self) -> None:
        from server.tournament.models import (
            Match,
            MatchEvent,
            MatchScore,
            MatchStats,
            SpiritScore,
            Tournament,
        )
        from server.tournament.schema import MatchSchema, MatchStatsSchema

        person = UCPerson.objects.create(
            email=EMAIL, slug="secret", first_name="Secret", last_name="Keeper"
        )
        self.player.ultimate_central_id = person.id
        self.player.save()
        teams = [Team.objects.create(name=n, slug=n) for n in ("one", "two")]
        tournament = Tournament.objects.create(event=create_event("Regionals"))
        spirit = {"rules": 2, "fouls": 2, "fair": 2, "positive": 2, "communication": 2}
        match = Match.objects.create(
            tournament=tournament,
            sequence_number=1,
            team_1=teams[0],
            team_2=teams[1],
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            suggested_score_team_1=MatchScore.objects.create(entered_by=self.player),
            spirit_score_team_1=SpiritScore.objects.create(
                **spirit, mvp=person, msp=person, mvp_v2=self.player, msp_v2=self.player
            ),
        )
        stats = MatchStats.objects.create(
            match=match,
            tournament=tournament,
            initial_possession=teams[0],
            current_possession=teams[0],
        )
        event = MatchEvent.objects.create(
            stats=stats, team=teams[0], started_on="OFF", type="SC", scored_by=self.player
        )
        event.players.add(self.player)

        for body in (
            MatchSchema.model_validate(match).model_dump_json(),
            MatchStatsSchema.model_validate(stats).model_dump_json(),
        ):
            for secret in (EMAIL, PHONE, DOB.isoformat()):
                self.assertNotIn(secret, body)
        # What the match card reads.
        card = MatchSchema.model_validate(match).model_dump()
        self.assertEqual("Secret Keeper", card["suggested_score_team_1"]["entered_by"]["full_name"])
        self.assertEqual("Secret Keeper", card["spirit_score_team_1"]["mvp_v2"]["full_name"])
        self.assertEqual("Secret", card["spirit_score_team_1"]["msp"]["first_name"])


class TestElectionCandidates(PlayerPrivacyTestCase):
    def test_only_staff_see_a_candidates_username(self) -> None:
        from django.utils import timezone

        from server.election.models import Candidate, Election

        election = Election.objects.create(
            title="Board",
            description="",
            start_date=timezone.now(),
            end_date=timezone.now() + datetime.timedelta(days=7),
        )
        Candidate.objects.create(election=election, user=self.owner, bio="Hello")
        url = f"/api/election/{election.id}/candidates/"

        for viewer in (None, self.stranger):
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(url)
            self.assertEqual(200, response.status_code, response.content)
            self.assert_no_secrets(response, viewer or self.stranger)
            # What the election page reads.
            self.assertEqual("Secret Keeper", response.json()[0]["user"]["full_name"])

        # The staff's candidate manager shows it.
        self.client.force_login(self.staff)
        self.assertEqual(EMAIL, self.client.get(url).json()[0]["user"]["username"])


class TestUsersNamedInResponses(PlayerPrivacyTestCase):
    """An author, an inviter, a ticket's people or a co-director: by name."""

    def test_an_announcements_author_is_named_without_their_email(self) -> None:
        from server.announcements.models import Announcement

        Announcement.objects.create(
            title="News", slug="news", content="Hi", author=self.owner, is_published=True
        )
        self.client.force_login(self.stranger)
        for url in ("/api/announcements/", "/api/announcements/news"):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code, response.content)
            self.assert_no_secrets(response, self.stranger)
        author = self.client.get("/api/announcements/news").json()["author"]
        # What the announcement pages read.
        self.assertEqual(("Secret", "Keeper"), (author["first_name"], author["last_name"]))

    def test_a_series_invitation_names_its_sender_without_their_email(self) -> None:
        from server.series.models import Series, SeriesRosterInvitation
        from server.series.schema import SeriesRosterInvitationSchema

        series = Series.objects.create(
            name="Club series",
            start_date="2026-10-01",
            end_date="2027-03-31",
            type=Series.Type.MIXED,
            category=Series.Category.CLUB,
            series_roster_max_players=30,
            event_min_players_male=0,
            event_min_players_female=0,
            event_max_players_male=20,
            event_max_players_female=20,
        )
        invitee = Player.objects.create(user=self.stranger, date_of_birth=datetime.date(1990, 1, 1))
        invitation = SeriesRosterInvitation.objects.create(
            series=series,
            from_user=self.owner,
            to_player=invitee,
            team=Team.objects.create(name="Inviters", slug="inviters"),
        )
        body = SeriesRosterInvitationSchema.model_validate(invitation).model_dump_json()
        for secret in (EMAIL, PHONE, DOB.isoformat()):
            self.assertNotIn(secret, body)
        # What the invitation pages read.
        self.assertIn('"full_name":"Secret Keeper"', body)

    def test_a_public_tickets_people_are_named_without_their_email(self) -> None:
        from server.ticket.models import Ticket, TicketMessage

        ticket = Ticket.objects.create(
            title="Help", description="Please", created_by=self.owner, assigned_to=self.owner
        )
        TicketMessage.objects.create(ticket=ticket, sender=self.owner, message="Hello")

        self.client.force_login(self.stranger)
        for url in ("/api/ticket/", f"/api/ticket/{ticket.id}"):
            response = self.client.get(url)
            self.assertEqual(200, response.status_code, response.content)
            self.assert_no_secrets(response, self.stranger)
        detail = self.client.get(f"/api/ticket/{ticket.id}").json()
        self.assertEqual("Secret", detail["created_by"]["first_name"])

        # Staff mail them from the ticket page.
        self.client.force_login(self.staff)
        detail = self.client.get(f"/api/ticket/{ticket.id}").json()
        self.assertEqual(EMAIL, detail["created_by"]["username"])
        self.assertEqual(EMAIL, detail["messages"][0]["sender"]["username"])

    def test_a_director_sees_co_directors_emails_masked(self) -> None:
        from server.tournament.models import Tournament

        tournament = Tournament.objects.create(event=create_event("Regionals"))
        tournament.directors.add(self.owner, self.stranger)
        url = f"/api/tournament/{tournament.id}/directors"

        self.client.force_login(self.stranger)
        response = self.client.get(url)
        self.assertEqual(200, response.status_code, response.content)
        self.assert_no_secrets(response, self.stranger)
        self.assertIn("hixxxxxxxxxet@example.org", {d["username"] for d in response.json()})

        self.client.force_login(self.staff)
        self.assertIn(EMAIL, {d["username"] for d in self.client.get(url).json()})


class TestLinkUltimateCentral(PlayerPrivacyTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Enough for the player to pass full_clean when linked.
        Player.objects.filter(id=self.player.id).update(gender="M", match_up="M")

    def link(self, viewer: User) -> Any:
        self.client.force_login(viewer)
        UCPerson.objects.get_or_create(
            id=4242,
            defaults={"email": "uc@x.com", "slug": "uc", "first_name": "U", "last_name": "C"},
        )
        with patch("server.api.TopScoreClient") as client:
            client.return_value.get_person.return_value = {"person_id": 4242}
            return self.client.post(
                "/api/upai/me",
                {"username": "u", "password": "p", "player_id": self.player.id},
                content_type="application/json",
            )

    def test_a_stranger_cannot_read_or_link_another_player(self) -> None:
        response = self.link(self.stranger)
        self.assertEqual(403, response.status_code)
        self.assert_no_secrets(response, self.stranger)
        self.player.refresh_from_db()
        self.assertIsNone(self.player.ultimate_central_id)

    def test_the_player_and_their_guardian_can_link(self) -> None:
        for viewer in (self.owner, self.guardian):
            Player.objects.filter(id=self.player.id).update(ultimate_central_id=None)
            response = self.link(viewer)
            self.assertEqual(200, response.status_code, response.content)
            self.player.refresh_from_db()
            self.assertEqual(4242, self.player.ultimate_central_id)
