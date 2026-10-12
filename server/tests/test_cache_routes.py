"""Which pages the cache keeps, and the tournament each is scoped to."""

import time
from unittest.mock import patch

from django.core.cache import cache

from server.cache import store
from server.tests.test_cache_store import CacheTestCase
from server.tournament.models import Tournament


class TestCacheRoutes(CacheTestCase):
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
        with self.assertNoLogs("server.cache", "WARNING"):
            status, _ = self.get_counting("/api/match/\u00b2")
        self.assertNotEqual(500, status)
        self.assertEqual([], self.page_keys())

    def test_other_routes_are_not_cached(self) -> None:
        self.client.get("/api/me")
        self.assertEqual([], self.page_keys())

    def test_a_recreated_tournament_is_not_followed_by_its_dead_id(self) -> None:
        url = self.pages["slug"]
        self.client.get(url)
        event = self.tournament.event
        self.tournament.delete()
        new = Tournament.objects.create(event=event)
        # The lookup may point at the dead id for one page TTL, not longer.
        with patch("time.time", return_value=time.time() + store.TTL + 1):
            self.assertEqual(200, self.client.get(url).status_code)
            with self.captureOnCommitCallbacks(execute=True):
                new.save()
            self.assertGreater(self.count_queries(url), 0)
