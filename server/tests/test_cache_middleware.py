"""Serving and storing the public pages."""

from collections.abc import Callable
from contextlib import suppress
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import TooManyFieldsSent
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from server.cache import middleware, store
from server.tests.test_cache_store import CacheTestCase


class TestCacheMiddleware(CacheTestCase):
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
        # A route the cache scopes, and a view that answers 200: only the
        # GET-only check keeps this out of the cache.
        request = RequestFactory().post(f"/api/match/{self.match.id}")
        response = middleware.PublicCacheMiddleware(lambda _: HttpResponse(b"{}", status=200))(
            request
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], self.page_keys())

    def test_a_malformed_entry_is_a_miss(self) -> None:
        url = self.pages["match"]
        first = self.client.get(url)
        (key,) = self.page_keys()
        for bad in ("junk", (b"x",), ("x", "text/plain"), (b"x", b"y"), None):
            cache.set(key.split(":", 2)[2], bad, 30)  # Strip Django's ":1:" prefix
            response = self.client.get(url)
            self.assertEqual(200, response.status_code, bad)
            self.assertEqual(first.content, response.content, bad)

    @property
    def lenient(self) -> Client:
        return Client(raise_request_exception=False)

    def test_a_failing_lookup_does_not_pause_the_cache(self) -> None:
        # A database error is the view's to report, not a cache outage.
        with (
            self.assertNoLogs("server.cache", "WARNING"),
            patch("django.db.models.query.QuerySet.first", side_effect=ValueError("nul")),
        ):
            response = self.lenient.get("/api/tournament?slug=anything")
        self.assertTrue(store.enabled())
        self.assertNotIn(response.status_code, (200,))

    def test_too_many_query_params_do_not_pause_the_cache(self) -> None:
        query = "&".join(f"p{i}=1" for i in range(1001))
        # The view's own answer; the error handler re-reads GET and raises.
        with self.assertNoLogs("server.cache", "WARNING"), suppress(TooManyFieldsSent):
            self.lenient.get(f"/api/tournament?{query}")
        self.assertTrue(store.enabled())

    def test_a_write_during_a_view_is_not_hidden(self) -> None:
        # The view's write lands after the version is read but before the page
        # is stored, so the stored page is already stale and must not be served.
        original = middleware.PublicCacheMiddleware.__init__
        tid = str(self.tournament.id)

        def init(
            instance: middleware.PublicCacheMiddleware,
            get_response: Callable[[HttpRequest], HttpResponse],
        ) -> None:
            def writing_view(request: HttpRequest) -> HttpResponse:
                response = get_response(request)
                with self.captureOnCommitCallbacks(execute=True):
                    store.bump(tid)
                return response

            original(instance, writing_view)

        url = self.pages["id"]
        with patch.object(middleware.PublicCacheMiddleware, "__init__", init):
            Client().get(url)  # Its own client, so self.client's views stay unpatched.
        self.assertGreater(self.count_queries(url), 0)
