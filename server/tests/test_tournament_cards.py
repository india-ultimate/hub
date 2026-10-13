"""Tournament cards for the public pages: by year, or the home page's recent few."""

import datetime
from typing import Any

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from server.tournament.models import Event, Tournament
from server.utils import today

DAY = datetime.timedelta(days=1)


def tournament(
    slug: str,
    start: datetime.date,
    end: datetime.date | None = None,
    status: str = Tournament.Status.SCHEDULING,
) -> Tournament:
    event = Event.objects.create(
        title=slug,
        slug=slug,
        start_date=start,
        end_date=end or start,
        team_registration_start_date=start - 30 * DAY,
        team_registration_end_date=start - 20 * DAY,
        player_registration_start_date=start - 19 * DAY,
        player_registration_end_date=start - DAY,
    )
    return Tournament.objects.create(event=event, status=status)


class TestTournamentCards(TestCase):
    def cards(self, query: str = "") -> dict[str, Any]:
        response = self.client.get(f"/api/tournaments/public{query}")
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def slugs(self, query: str = "") -> set[str]:
        return {t["event"]["slug"] for t in self.cards(query)["tournaments"]}

    def test_cards_carry_the_tags(self) -> None:
        t = tournament("beach", today() + 5 * DAY)
        Event.objects.filter(pk=t.event_id).update(surface="Beach", is_iu_sanctioned=True)
        (card,) = self.cards()["tournaments"]
        self.assertEqual("Beach", card["event"]["surface"])
        self.assertIs(True, card["event"]["is_iu_sanctioned"])
        self.assertIsNone(card["event"]["age"])

    def test_a_year_has_only_its_tournaments(self) -> None:
        tournament("in-2024", datetime.date(2024, 5, 1))
        tournament("in-2025", datetime.date(2025, 5, 1))
        self.assertEqual({"in-2024"}, self.slugs("?year=2024"))

    def test_years_are_those_with_published_tournaments(self) -> None:
        tournament("in-2024", datetime.date(2024, 5, 1))
        tournament("in-2025", datetime.date(2025, 5, 1))
        tournament("draft-2023", datetime.date(2023, 5, 1), status=Tournament.Status.DRAFT)
        self.assertEqual([2025, 2024], self.cards("?year=2024")["years"])

    def test_drafts_are_left_out_of_years(self) -> None:
        tournament("draft", datetime.date(2024, 5, 1), status=Tournament.Status.DRAFT)
        self.assertEqual(set(), self.slugs("?year=2024"))

    def test_default_is_this_year_and_upcoming(self) -> None:
        day = today()
        tournament("this-year", datetime.date(day.year, 1, 1))
        tournament("last-year", datetime.date(day.year - 1, 6, 1))
        tournament("next-year", datetime.date(day.year + 1, 1, 10))
        self.assertEqual({"this-year", "next-year"}, self.slugs())

    def test_default_includes_upcoming_next_year(self) -> None:
        tournament("soon", today() + 20 * DAY)
        self.assertEqual({"soon"}, self.slugs())

    def test_recent(self) -> None:
        # The server sends a superset (window plus the 2 latest ended); the home page filters it.
        day = today()
        tournament("live", day - DAY, day + DAY)
        tournament("upcoming", day + 20 * DAY)
        tournament("last-month", day - 30 * DAY)
        tournament("long-ago", day - 400 * DAY)
        tournament("older", day - 500 * DAY)
        self.assertEqual({"live", "upcoming", "last-month", "long-ago"}, self.slugs("?recent=1"))

    def test_recent_keeps_the_last_two_when_nothing_ended_lately(self) -> None:
        day = today()
        tournament("old-1", day - 200 * DAY)
        tournament("old-2", day - 300 * DAY)
        tournament("old-3", day - 400 * DAY)
        self.assertEqual({"old-1", "old-2"}, self.slugs("?recent=1"))

    def test_recent_includes_drafts(self) -> None:
        # The home page lists drafts (linking to the tournament, not registration).
        tournament("draft", today() + 20 * DAY, status=Tournament.Status.DRAFT)
        self.assertEqual({"draft"}, self.slugs("?recent=1"))

    def test_a_card_has_what_the_pages_read(self) -> None:
        tournament("card", today() + 20 * DAY)
        (card,) = self.cards()["tournaments"]
        self.assertEqual({"id", "status", "logo_light", "logo_dark", "event"}, set(card))
        for key in (
            "type",
            "title",
            "location",
            "slug",
            "start_date",
            "end_date",
            "team_registration_start_date",
            "team_registration_end_date",
            "team_late_penalty_end_date",
            "player_registration_start_date",
            "player_registration_end_date",
            "player_late_penalty_end_date",
            "series",
        ):
            self.assertIn(key, card["event"])
        self.assertNotIn("rules", card)

    def test_newest_first(self) -> None:
        day = today()
        tournament("later", day + 30 * DAY)
        tournament("sooner", day + 10 * DAY)
        slugs = [t["event"]["slug"] for t in self.cards()["tournaments"]]
        self.assertEqual(["later", "sooner"], slugs)

    def test_no_tournaments(self) -> None:
        self.assertEqual({"years": [], "tournaments": []}, self.cards())

    def test_a_bad_year(self) -> None:
        for year in ("abc", "0", "-1", "10000"):
            with self.subTest(year=year):
                self.assertEqual(
                    422, self.client.get(f"/api/tournaments/public?year={year}").status_code
                )

    def test_queries_dont_grow(self) -> None:
        def count() -> int:
            with CaptureQueriesContext(connection) as queries:
                self.cards("?recent=1")
                self.cards("?year=2024")
            return len(queries.captured_queries)

        tournament("a", today())
        before = count()
        for i in range(5):
            tournament(f"more-{i}", today() + i * DAY)
        self.assertEqual(before, count())
