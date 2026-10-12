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
        pill = 'button[role="radio"]:contains("{}")'
        self.click(pill.format(last_year))
        self.assert_element(old)
        self.assert_element_not_present(soon)
        self.assertIn(f"?year={last_year}", self.get_current_url())
        self.click(pill.format(last_year - 1))
        self.assert_element(older)
        self.assert_element_not_present(old)
        self.click(pill.format("This year"))
        self.assert_element(soon)
        self.assertNotIn("year=", self.get_current_url())

    def test_a_year_in_the_link_opens_on_that_year(self) -> None:
        last_year = today().year - 1
        old = self.held("Old Nationals", datetime.date(last_year, 6, 1))
        soon = self.held("Soon Nationals", today() + 20 * DAY)
        self.open(f"{APP_URL}/tournaments?year={last_year}")
        self.assert_element(old)
        self.assert_element_not_present(soon)
        self.assert_element(f'button[role="radio"][aria-checked="true"]:contains("{last_year}")')

    def test_a_year_with_nothing_says_so(self) -> None:
        last_year = today().year - 1
        self.held("Old Nationals", datetime.date(last_year, 6, 1))
        self.open(f"{APP_URL}/tournaments?year={last_year}")
        self.click('button[aria-pressed="true"]:contains("Opens")')
        self.assert_text("No tournaments match these filters")

    def test_a_year_that_is_not_one_shows_the_default_view(self) -> None:
        soon = self.held("Soon Nationals", today() + 20 * DAY)
        for bad in ("abc", "0", "10000"):
            self.open(f"{APP_URL}/tournaments?year={bad}")
            self.assert_element(soon)
            self.assert_element('button[role="radio"][aria-checked="true"]:contains("This year")')
            self.assert_element_not_present('[role="alert"]')

    def test_an_unlisted_year_leaves_the_pills_reachable_by_keyboard(self) -> None:
        self.held("Old Nationals", datetime.date(today().year - 1, 6, 1))
        self.open(f"{APP_URL}/tournaments?year=2099")
        self.assert_element('button[role="radio"][tabindex="0"]:contains("This year")')
        self.assert_element_not_present('button[role="radio"][aria-checked="true"]')

    def test_a_pill_replaces_the_history_entry(self) -> None:
        last_year = today().year - 1
        self.held("Old Nationals", datetime.date(last_year, 6, 1))
        self.open(f"{APP_URL}/tournaments")
        entries = self.execute_script("return history.length")
        self.click(f'button[role="radio"]:contains("{last_year}")')
        self.assert_element(f'button[aria-checked="true"]:contains("{last_year}")')
        self.assertEqual(entries, self.execute_script("return history.length"))

    def test_a_deep_linked_old_year_is_scrolled_into_view(self) -> None:
        this_year = today().year
        for year in range(this_year - 1, this_year - 9, -1):
            self.held(f"Nationals {year}", datetime.date(year, 6, 1))
        self.set_window_size(500, 800)
        self.open(f"{APP_URL}/tournaments?year={this_year - 8}")
        self.assert_element(f'button[aria-checked="true"]:contains("{this_year - 8}")')
        self.sleep(1)
        on_screen = self.execute_script(
            "const r = document.querySelector('[aria-checked=true]').getBoundingClientRect();"
            "return r.left >= 0 && r.right <= innerWidth"
        )
        self.assertTrue(on_screen)
        self.assertEqual(0, self.execute_script("return scrollY"))

    def test_a_failed_load_says_so(self) -> None:
        self.held("Old Nationals", datetime.date(today().year - 1, 6, 1))
        self.open(f"{APP_URL}/tournaments")
        self.assert_element('button[role="radio"]:contains("This year")')
        self.execute_script(
            "window.fetch = () => Promise.resolve(new Response('{}', {status: 500}))"
        )
        self.click(f'button[role="radio"]:contains("{today().year - 1}")')
        self.assert_text("Couldn't load the tournaments", timeout=30)

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
