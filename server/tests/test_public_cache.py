"""The shared cache for public tournament pages."""

from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from server.tests.test_tournament_api_perf import TournamentApiTestCase

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class TestPublicCache(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        self.match = self.make_match()
        slug = self.tournament.event.slug
        self.pages = {
            "all": "/api/tournaments/public",
            "id": f"/api/tournament/{self.tournament.id}/matches",
            "query id": f"/api/tournament?id={self.tournament.id}",
            "slug": f"/api/tournament/slug/{slug}/matches",
            "query slug": f"/api/tournament/pools?slug={slug}",
            "match": f"/api/match/{self.match.id}",
            "roster": f"/api/v2/tournament/{slug}/team/{self.team_1.slug}/roster",
        }

    def get_counting(self, url: str) -> tuple[int, int]:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        return response.status_code, len(queries.captured_queries)

    def page_keys(self) -> list[str]:
        return [k for k in cache._cache if "page:" in k]  # type: ignore[attr-defined]

    def test_a_second_get_runs_no_queries(self) -> None:
        for name, url in self.pages.items():
            first = self.client.get(url)
            self.assertEqual(200, first.status_code, name)
            self.assertEqual(0, self.count_queries(url), name)
            self.assertEqual(first.content, self.client.get(url).content, name)

    def test_a_hit_keeps_the_content_type_and_sets_no_cookie(self) -> None:
        url = self.pages["match"]
        self.client.get(url)
        hit = self.client.get(url)
        self.assertEqual("application/json; charset=utf-8", hit["Content-Type"])
        self.assertFalse(hit.cookies)

    def test_errors_are_not_cached(self) -> None:
        # The id and slug lookups reach their view, which queries each time.
        for url in ("/api/match/999999", "/api/tournament?slug=nope"):
            for attempt in ("first", "second"):
                status, queries = self.get_counting(url)
                self.assertNotEqual(200, status, f"{url} {attempt}")
                self.assertGreater(queries, 0, f"{url} {attempt}")
        # A non-numeric id is refused by validation before any query.
        for attempt in ("first", "second"):
            status, _ = self.get_counting("/api/tournament/abc/matches")
            self.assertNotEqual(200, status, attempt)

    def test_a_failed_view_is_not_cached(self) -> None:
        # An id scope needs no lookup, so this reaches the view, which says 400.
        url = "/api/tournament/cross-pool?id=999999"
        for attempt in ("first", "second"):
            status, queries = self.get_counting(url)
            self.assertEqual(400, status, attempt)
            self.assertGreater(queries, 0, attempt)

    def test_a_write_method_is_never_stored(self) -> None:
        self.client.delete(f"/api/match/{self.match.id}")
        self.assertEqual([], self.page_keys())

    def scoped_to(self, url: str, tid: int) -> None:
        self.client.get(url)
        self.assertEqual(1, len(self.page_keys()), url)
        self.assertIn(f"page:{tid}:0:", self.page_keys()[0])

    def test_a_route_is_scoped_by_the_input_its_view_reads(self) -> None:
        slug, tid = self.tournament.event.slug, self.tournament.id
        # A path route ignores ?id=; the pools view reads the slug when id is 0.
        for url in (
            f"/api/tournament/slug/{slug}/matches?id=5",
            f"/api/tournament/pools?id=0&slug={slug}",
        ):
            cache.clear()
            self.scoped_to(url, tid)

    def test_ids_are_normalised(self) -> None:
        tid = self.tournament.id
        self.scoped_to(f"/api/tournament?id=0{tid}", tid)

    def test_a_non_ascii_digit_id_is_not_an_error(self) -> None:
        with self.assertNoLogs("server.public_cache", "WARNING"):
            status, _ = self.get_counting("/api/match/\u00b2")
        self.assertNotEqual(500, status)
        self.assertEqual([], self.page_keys())

    def test_other_routes_are_not_cached(self) -> None:
        self.client.get("/api/me")
        self.assertEqual([], self.page_keys())


class TestPublicCacheOff(TournamentApiTestCase):
    def test_off_without_redis(self) -> None:
        url = f"/api/match/{self.make_match().id}"
        self.client.get(url)
        self.assertGreater(self.count_queries(url), 0)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:1/0",
            "OPTIONS": {"socket_connect_timeout": 0.1, "socket_timeout": 0.2},
        }
    }
)
class TestRedisDown(TournamentApiTestCase):
    def test_pages_load_when_redis_is_down(self) -> None:
        url = f"/api/match/{self.make_match().id}"
        with self.assertLogs("server.public_cache", "WARNING"):
            response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.team_1.slug, response.json()["team_1"]["slug"])

    def test_one_failing_call_per_request(self) -> None:
        url = f"/api/tournament/{self.tournament.id}/matches"
        with self.assertLogs("server.public_cache", "WARNING") as logs:
            self.assertEqual(200, self.client.get(url).status_code)
        self.assertEqual(1, len(logs.records))
