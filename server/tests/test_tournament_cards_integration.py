"""The public pages fetch only the tournaments they show."""

import datetime
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Tournament
from server.utils import today

DAY = datetime.timedelta(days=1)


@pytest.mark.django_db(transaction=True)
class TestTournamentCardsIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def held(self, title: str, start: datetime.date) -> str:
        event = open_event(
            title=title,
            type="OPN",
            start_date=start,
            end_date=start,
            team_registration_start_date=start - 30 * DAY,
            team_registration_end_date=start - 20 * DAY,
            player_registration_start_date=start - 19 * DAY,
            player_registration_end_date=start - DAY,
        )
        Tournament.objects.create(event=event, status=Tournament.Status.COMPLETED)
        return f'a[href^="/tournament/{event.slug}"]'

    def test_the_year_picker_shows_that_years_tournaments(self) -> None:
        last_year = today().year - 1
        old = self.held("Old Nationals", datetime.date(last_year, 6, 1))
        older = self.held("Older Nationals", datetime.date(last_year - 1, 6, 1))
        soon = self.held("Soon Nationals", today() + 20 * DAY)
        self.open(f"{APP_URL}/tournaments")
        self.assert_element(soon)
        self.assert_element_not_present(old)
        self.select_option_by_text('select[aria-label="Year"]', str(last_year))
        self.assert_element(old)
        self.assert_element_not_present(soon)
        self.select_option_by_text('select[aria-label="Year"]', str(last_year - 1))
        self.assert_element(older)
        self.assert_element_not_present(old)

    def test_the_home_page_shows_live_upcoming_and_past(self) -> None:
        day = today()
        live = open_event(title="Live Open", type="OPN", start_date=day, end_date=day + DAY)
        Tournament.objects.create(event=live, status=Tournament.Status.LIVE)
        upcoming = open_event(title="Upcoming Open", type="OPN")
        Tournament.objects.create(event=upcoming, status=Tournament.Status.SCHEDULING)
        past = self.held("Past Open", day - 10 * DAY)
        long_ago = self.held("Long Ago Open", day - 400 * DAY)
        self.open(APP_URL)
        self.assert_text("Live Tournaments")
        self.assert_element(f'a[href^="/tournament/{live.slug}"]')
        self.assert_text("Upcoming Tournaments")
        self.assert_element(f'a[href^="/tournament/{upcoming.slug}"]')
        self.assert_text("Past Tournaments")
        self.assert_element(past)
        self.assert_element_not_present(long_ago)
