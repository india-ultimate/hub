"""Serving and storing the public pages."""

from collections.abc import Callable
from unittest.mock import patch

from django.http import HttpRequest, HttpResponse
from django.test import Client

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
        self.client.delete(f"/api/match/{self.match.id}")
        self.assertEqual([], self.page_keys())

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
