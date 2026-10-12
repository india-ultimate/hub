"""The page cache's Redis layer: bumps, fail-open and the pause."""

import time
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

from django.core.cache import cache, caches
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from server.cache import store
from server.tests.test_tournament_api_perf import TournamentApiTestCase

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class CacheTestCase(TournamentApiTestCase):
    """A fresh, working cache and one match, with a page of each scope."""

    def setUp(self) -> None:
        super().setUp()
        store.reset()
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


class TestCacheStore(CacheTestCase):
    def test_one_bump_is_one_cache_call(self) -> None:
        calls: list[str] = []
        backend = type(caches["default"])
        names = ("get", "set", "add", "incr", "get_many", "set_many", "delete")
        patches = [
            patch.object(backend, n, autospec=True, side_effect=self.recorder(backend, n, calls))
            for n in names
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with self.captureOnCommitCallbacks(execute=True):
                store.bump("7")
        self.assertEqual(["set"], calls)
        self.assertEqual(1, len(self.version_keys()))

    @staticmethod
    def recorder(backend: Any, name: str, calls: list[str]) -> Callable[..., Any]:
        real = getattr(backend, name)

        def call(*args: Any, **kwargs: Any) -> Any:
            calls.append(name)
            return real(*args, **kwargs)

        return call

    def version_keys(self) -> list[str]:
        return [k for k in cache._cache if "tver:" in k]  # type: ignore[attr-defined]


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
    def setUp(self) -> None:
        super().setUp()
        store.reset()
        self.addCleanup(store.reset)

    def test_pages_load_when_redis_is_down(self) -> None:
        url = f"/api/match/{self.make_match().id}"
        with self.assertLogs("server.cache", "WARNING"):
            response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.team_1.slug, response.json()["team_1"]["slug"])

    def test_one_failing_call_per_request(self) -> None:
        url = f"/api/tournament/{self.tournament.id}/matches"
        with self.assertLogs("server.cache", "WARNING") as logs:
            self.assertEqual(200, self.client.get(url).status_code)
        self.assertEqual(1, len(logs.records))

    def test_after_a_failure_the_cache_is_skipped_for_five_seconds(self) -> None:
        url = f"/api/tournament/{self.tournament.id}/matches"
        backend = type(caches["default"])
        with self.assertLogs("server.cache", "WARNING"):
            first = self.client.get(url)
        with (
            patch.object(backend, "get", side_effect=AssertionError) as get,
            patch.object(backend, "set", side_effect=AssertionError) as put,
            self.assertNoLogs("server.cache", "WARNING"),
        ):
            second = self.client.get(url)
            self.assertFalse(store.enabled())
            with self.captureOnCommitCallbacks(execute=True):
                store.bump("1")
        self.assertEqual(200, second.status_code)
        self.assertEqual(first.content, second.content)
        self.assertEqual(0, get.call_count + put.call_count)

    def test_the_cache_is_tried_again_after_five_seconds(self) -> None:
        url = f"/api/tournament/{self.tournament.id}/matches"
        now = time.monotonic()
        with self.assertLogs("server.cache", "WARNING"):
            self.client.get(url)
        with (
            patch("server.cache.store.time.monotonic", return_value=now + 6),
            self.assertLogs("server.cache", "WARNING"),
        ):
            self.assertTrue(store.enabled())
            self.assertEqual(200, self.client.get(url).status_code)
