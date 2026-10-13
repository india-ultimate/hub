"""Tournament tags: the seal and chips on cards and pages, and the filters."""

import datetime
from contextlib import ExitStack
from typing import Any

import pytest
from seleniumbase import BaseCase

from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Event, Tournament
from server.utils import today

DAY = datetime.timedelta(days=1)
SEAL = "Sanctioned by India Ultimate"


@pytest.mark.django_db(transaction=True)
class TestTournamentTagsIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def held(self, title: str, start: datetime.date | None = None, **tags: Any) -> Event:
        start = start or today() + 20 * DAY
        event = open_event(
            title=title,
            type="OPN",
            start_date=start,
            end_date=start,
            team_registration_start_date=start - 30 * DAY,
            team_registration_end_date=start - 20 * DAY,
            player_registration_start_date=start - 19 * DAY,
            player_registration_end_date=start - DAY,
            **tags,
        )
        Tournament.objects.create(event=event, status=Tournament.Status.COMPLETED)
        return event

    def card(self, event: Event) -> str:
        return f'a[href^="/tournament/{event.slug}"]'

    def test_cards_show_the_seal_and_what_stands_out(self) -> None:
        beach = self.card(
            self.held(
                "Beach Nats", is_iu_sanctioned=True, surface="Beach", age="U24", stage="Nationals"
            )
        )
        plain = self.card(
            self.held("Club Open", surface="Grass", age="Open", stage="Standalone", level="Club")
        )
        self.open(f"{APP_URL}/tournaments")
        self.assert_element(f'{beach} h5 .sr-only:contains("{SEAL}")')
        for text in ("Beach", "U24", "Nationals"):
            self.assert_element(f'{beach} li:contains("{text}")')
        self.assert_element_not_present(f"{plain} h5 .sr-only")
        self.assert_element_not_present(f"{plain} li")

    def test_the_page_shows_every_tag_and_links_to_the_list(self) -> None:
        event = self.held(
            "Beach Nats",
            is_iu_sanctioned=True,
            surface="Beach",
            age="Open",
            stage="Nationals",
            level="Club",
            format="5v5",
            is_adaptive=True,
        )
        self.open(f"{APP_URL}/tournament/{event.slug}")
        self.assert_element(f'a[href="/tournaments?iu=1"]:contains("{SEAL}")')
        self.assert_text("An official India Ultimate event.")
        for text in ("Beach", "Open", "Nationals", "Club", "5v5", "Adaptive"):
            self.assert_element(f'li:contains("{text}")')
        self.click('li a:contains("Beach")')
        self.assert_element(self.card(event))
        self.assertIn("surface=Beach", self.get_current_url())

    def test_surface_and_age_combine(self) -> None:
        beach_u24 = self.card(self.held("Beach U24", surface="Beach", age="U24"))
        beach_open = self.card(self.held("Beach Open", surface="Beach", age="Open"))
        untagged = self.card(self.held("Untagged"))
        self.open(f"{APP_URL}/tournaments")
        self.click("details#more-filters summary")
        self.click('button[aria-pressed="false"]:contains("Beach")')
        self.assert_element(beach_u24)
        self.assert_element(beach_open)
        self.assert_element_not_present(untagged)
        self.click('button[aria-pressed="false"]:contains("U24")')
        self.assert_element(beach_u24)
        self.assert_element_not_present(beach_open)
        url = self.get_current_url()
        self.assertIn("surface=Beach", url)
        self.assertIn("age=U24", url)
        self.open(url)
        self.assert_element("details#more-filters[open]")
        self.assert_element('details#more-filters summary:contains("2 active")')
        self.assert_element_not_present(beach_open)
        self.click('button:contains("Clear filters")')
        self.assert_element(untagged)
        self.assertNotIn("surface=", self.get_current_url())

    def test_sanctioned_only(self) -> None:
        iu = self.card(self.held("IU Nats", is_iu_sanctioned=True))
        club = self.card(self.held("Club Open", is_iu_sanctioned=False))
        self.open(f"{APP_URL}/tournaments?iu=1")
        self.assert_element(iu)
        self.assert_element_not_present(club)
        self.assert_element(f'button[aria-pressed="true"]:contains("{SEAL}")')

    def test_junk_in_the_url_is_ignored(self) -> None:
        beach = self.card(self.held("Beach Open", surface="Beach", age="U24"))
        grass = self.card(self.held("Grass Open", surface="Grass"))
        self.open(f"{APP_URL}/tournaments?surface=Moon&age=U24,,X&iu=yes")
        self.assert_element(beach)
        self.assert_element_not_present(grass)
        self.assert_element('details#more-filters summary:contains("1 active")')
        self.assert_element_not_present('[role="alert"]')

    def test_clearing_keeps_the_year(self) -> None:
        last_year = today().year - 1
        event = self.held("Old Beach", start=datetime.date(last_year, 6, 1), surface="Beach")
        self.open(f"{APP_URL}/tournaments?surface=Beach")
        self.click(f'button[role="radio"]:contains("{last_year}")')
        self.assert_element(self.card(event))
        self.assertIn("surface=Beach", self.get_current_url())
        self.click('button:contains("Clear filters")')
        self.assertIn(f"year={last_year}", self.get_current_url())
        self.assertNotIn("surface=", self.get_current_url())

    def test_no_match_says_so_and_clears(self) -> None:
        self.held("Grass Open", surface="Grass")
        self.open(f"{APP_URL}/tournaments?surface=Beach")
        self.assert_text("No tournaments match these filters")
        self.click('button:contains("Clear filters")')
        self.assert_element_not_present('p:contains("No tournaments match")')
