"""A tournament's card on /tournaments: where it takes you, and its badge."""

import datetime
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Tournament
from server.utils import today


@pytest.mark.django_db(transaction=True)
class TestTournamentLinksIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def card(self, tournament: Tournament) -> str:
        self.open(f"{APP_URL}/tournaments")
        card = f'a[href^="/tournament/{tournament.event.slug}"]'
        self.assert_element(card)
        return card

    def card_link(self, tournament: Tournament) -> str:
        card = self.card(tournament)
        return str(self.get_attribute(card, "href", hard_fail=True)).removeprefix(APP_URL)

    def test_a_tournament_taking_registrations_opens_on_registration(self) -> None:
        # NOCS and NWCS opened on the tournament page, below the schedule.
        event = open_event(title="Nationals", type="OPN")
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.SCHEDULING)
        self.assertEqual(f"/tournament/{event.slug}/register", self.card_link(tournament))

    def test_one_where_only_players_can_still_register_does_too(self) -> None:
        day = today()
        event = open_event(
            title="Nationals",
            type="WMN",
            team_registration_start_date=day - datetime.timedelta(days=20),
            team_registration_end_date=day - datetime.timedelta(days=5),
        )
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.SCHEDULING)
        self.assertEqual(f"/tournament/{event.slug}/register", self.card_link(tournament))

    def test_a_live_tournament_opens_on_the_tournament_page(self) -> None:
        event = open_event(title="Nationals", type="MXD")
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.LIVE)
        self.assertEqual(f"/tournament/{event.slug}", self.card_link(tournament))

    def test_a_live_tournament_that_hasnt_started_says_upcoming(self) -> None:
        # Live means its schedule is out; the badge said "Live" weeks ahead.
        event = open_event(title="Nationals", type="OPN")  # starts in 20 days
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.LIVE)
        self.assert_text("Upcoming", self.card(tournament))

    def test_one_that_has_started_says_live(self) -> None:
        day = today()
        event = open_event(title="Nationals", type="OPN", start_date=day, end_date=day)
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.LIVE)
        card = self.card(tournament)
        self.assert_text("Live", card)
        self.assert_text_not_visible("Upcoming", card)

    def test_a_draft_on_the_home_page_is_not_sent_to_registration(self) -> None:
        # The home page lists drafts too; their registration isn't published.
        event = open_event(title="Nationals", type="OPN")
        Tournament.objects.create(event=event, status=Tournament.Status.DRAFT)
        self.open(APP_URL)
        card = f'a[href^="/tournament/{event.slug}"]'
        self.assert_element(card)
        href = str(self.get_attribute(card, "href", hard_fail=True)).removeprefix(APP_URL)
        self.assertEqual(f"/tournament/{event.slug}", href)

    def test_the_tournament_page_offers_player_registration(self) -> None:
        day = today()
        event = open_event(
            title="Nationals",
            type="OPN",
            team_registration_start_date=day - datetime.timedelta(days=20),
            team_registration_end_date=day - datetime.timedelta(days=5),
        )
        Tournament.objects.create(event=event, status=Tournament.Status.SCHEDULING)
        self.open(f"{APP_URL}/tournament/{event.slug}")
        self.assert_element(f'a[href="/tournament/{event.slug}/register"]')
        self.assert_text("Player Registrations")
