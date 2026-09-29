import datetime
from itertools import pairwise
from unittest import mock

from django.test import TestCase

from server.season.models import Season


class TestSeasonCurrent(TestCase):
    def setUp(self) -> None:
        # Named and dated well clear of the real seasons migration 0145
        # creates, so this test controls its own timeline.
        self.s30 = Season.objects.create(
            name="Test Season 2030-2031", start_date="2030-08-01", end_date="2031-07-31"
        )
        self.s31 = Season.objects.create(
            name="Test Season 2031-2032", start_date="2031-08-01", end_date="2032-07-31"
        )

    def test_current_is_the_season_containing_today(self) -> None:
        with mock.patch("server.season.models.today", return_value=datetime.date(2031, 9, 25)):
            self.assertEqual(Season.current(), self.s31)

    def test_a_newer_season_does_not_become_current_early(self) -> None:
        # The frontend takes the newest start_date, which is wrong the moment
        # someone creates next season ahead of time.
        Season.objects.create(
            name="Test Season 2032-2033", start_date="2032-08-01", end_date="2033-07-31"
        )
        with mock.patch("server.season.models.today", return_value=datetime.date(2031, 9, 25)):
            self.assertEqual(Season.current(), self.s31)

    def test_boundary_days_are_inside_the_season(self) -> None:
        for day, expected in [
            (datetime.date(2031, 8, 1), self.s31),
            (datetime.date(2031, 7, 31), self.s30),
            # The day after s31.end_date, with nothing later to cover it:
            # this only fails if end_date__gte is dropped, since start_date
            # alone (plus ordering by -start_date) would still pick s31.
            (datetime.date(2032, 8, 1), None),
        ]:
            with mock.patch("server.season.models.today", return_value=day):
                self.assertEqual(Season.current(), expected)

    def test_no_season_covers_the_day(self) -> None:
        with mock.patch("server.season.models.today", return_value=datetime.date(2019, 1, 1)):
            self.assertIsNone(Season.current())

    def test_no_current_season_logs_a_warning(self) -> None:
        with (
            mock.patch("server.season.models.today", return_value=datetime.date(2019, 1, 1)),
            self.assertLogs("server.season.models", level="WARNING") as logs,
        ):
            self.assertIsNone(Season.current())
        self.assertIn("no season", logs.output[0].lower())

    def test_overlap_breaks_the_tie_by_start_date_not_by_row_order(self) -> None:
        # `early` is created first, so it has the lower pk, but `late` has
        # the later start_date and should win: the pk order and the
        # required tie-break disagree here, so a bare, unordered `.first()`
        # would return the wrong one (`early`).
        early = Season.objects.create(
            name="Test Season Overlap Early", start_date="2040-01-01", end_date="2040-12-31"
        )
        late = Season.objects.create(
            name="Test Season Overlap Late", start_date="2040-06-01", end_date="2041-05-31"
        )
        with mock.patch("server.season.models.today", return_value=datetime.date(2040, 7, 1)):
            self.assertEqual(Season.current(), late)
            self.assertNotEqual(Season.current(), early)


class TestCurrentSeasonApi(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.create(
            name="Test Season 2031-2032", start_date="2031-08-01", end_date="2032-07-31"
        )

    def get(self, day: datetime.date) -> "tuple[int, dict[str, object]]":
        with mock.patch("server.season.models.today", return_value=day):
            response = self.client.get("/api/seasons/current")
        return response.status_code, response.json()

    def test_it_answers_with_the_season_containing_today(self) -> None:
        status, body = self.get(datetime.date(2031, 9, 25))
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], self.season.name)
        self.assertEqual(body["id"], self.season.id)

    def test_a_season_that_has_not_started_is_not_answered_early(self) -> None:
        Season.objects.create(
            name="Test Season 2032-2033", start_date="2032-08-01", end_date="2033-07-31"
        )
        status, body = self.get(datetime.date(2031, 9, 25))
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], self.season.name)

    def test_no_season_covering_today_is_a_404_not_an_empty_season(self) -> None:
        status, _ = self.get(datetime.date(2019, 1, 1))
        self.assertEqual(status, 404)

    def test_it_needs_no_login(self) -> None:
        status, _ = self.get(datetime.date(2031, 9, 25))
        self.assertEqual(status, 200)


REAL_SEASON_NAMES = [
    "Season 2022-2023",
    "Season 2023-2024",
    "Season 2024-2025",
    "Season 2025-2026",
    "Season 2026-2027",
]


class TestLegacySeasons(TestCase):
    def test_the_timeline_is_continuous_from_2022(self) -> None:
        # Migration 0145 has already run against the test database. Scoped to
        # the five real seasons by name: other tests create their own seasons
        # with arbitrary dates, which would make an all-rows assertion flap.
        seasons = list(Season.objects.filter(name__in=REAL_SEASON_NAMES).order_by("start_date"))
        self.assertEqual(len(seasons), len(REAL_SEASON_NAMES))
        for earlier, later in pairwise(seasons):
            self.assertEqual(
                (later.start_date - earlier.end_date).days,
                1,
                f"gap between {earlier.name} and {later.name}",
            )
