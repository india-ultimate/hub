"""The shared cache for public tournament pages."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext

from server import public_cache
from server.core.models import Team
from server.tests.base import create_event
from server.tests.test_tournament_api_perf import TournamentApiTestCase
from server.tournament.models import Match, MatchEvent, Registration, Tournament

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def saving(row: Model | None) -> Callable[[], None]:
    assert row is not None  # noqa: S101 - make_match fills every relation
    return row.save


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

    def assert_fresh_after(self, url: str, write: Callable[[], Any]) -> None:
        self.client.get(url)
        self.assertEqual(0, self.count_queries(url))
        with self.captureOnCommitCallbacks(execute=True):
            write()
        self.assertGreater(self.count_queries(url), 0)

    def test_a_score_through_the_api_shows_on_the_next_get(self) -> None:
        url = self.pages["id"]
        # A scheduled match takes a score. The fixture's stages have no seeding to
        # score against, so the match leaves them and they go.
        self.match.status = Match.Status.SCHEDULED
        for stage in ("pool", "cross_pool", "bracket", "position_pool", "swiss_round"):
            setattr(self.match, stage, None)
        self.match.save()
        for row in (self.pool, self.cross_pool, self.bracket, self.position_pool, self.swiss_round):
            row.delete()
        self.client.get(url)
        self.client.force_login(self.user)
        self.user.is_staff = True
        self.user.save()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(
                f"/api/match/{self.match.id}/score",
                {"team_1_score": 7, "team_2_score": 3},
                content_type="application/json",
            )
        self.assertEqual(200, r.status_code, r.content)
        self.client.logout()
        (match,) = self.client.get(url).json()
        self.assertEqual(7, match["score_team_1"])

    def test_a_match_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["match"], self.match.save)

    def test_a_spirit_score_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["match"], saving(self.match.spirit_score_team_1))

    def test_a_suggested_score_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["match"], saving(self.match.suggested_score_team_1))

    def test_a_stats_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["match"], self.match.stats.save)

    def test_a_new_match_event_refreshes(self) -> None:
        def write() -> None:
            MatchEvent.objects.create(
                stats=self.match.stats, team=self.team_1, type=MatchEvent.EventType.SCORE
            )

        self.assert_fresh_after(self.pages["match"], write)

    def test_a_pool_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["query id"], self.pool.save)

    def test_a_field_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["id"], saving(self.match.field))

    def test_a_tournament_save_refreshes(self) -> None:
        self.assert_fresh_after(self.pages["query id"], self.tournament.save)

    def test_an_event_save_refreshes_its_tournament_and_the_lists(self) -> None:
        self.assert_fresh_after(self.pages["slug"], self.event.save)
        self.assert_fresh_after(self.pages["all"], self.event.save)

    def test_a_registration_refreshes_the_roster(self) -> None:
        def write() -> None:
            Registration.objects.create(event=self.event, team=self.team_1, player=self.player)

        self.assert_fresh_after(self.pages["roster"], write)

    def test_a_team_added_to_the_tournament_refreshes(self) -> None:
        def write() -> None:
            self.tournament.teams.add(Team.objects.create(name="Newcomers"))

        self.assert_fresh_after(self.pages["query id"], write)

    def test_a_tournament_added_to_a_team_refreshes(self) -> None:
        def write() -> None:
            # Through partial_teams: teams.through's seeding receiver assumes a tournament.
            team = Team.objects.create(name="Newcomers")
            team.partial_reg_tournaments.add(self.tournament)

        self.assert_fresh_after(self.pages["query id"], write)

    def test_a_team_clearing_its_tournaments_refreshes(self) -> None:
        self.tournament.partial_teams.add(self.team_2)
        self.assert_fresh_after(self.pages["query id"], self.team_2.partial_reg_tournaments.clear)

    def test_a_team_rename_refreshes(self) -> None:
        def write() -> None:
            self.team_1.name = "Renamed"
            self.team_1.save()

        self.assert_fresh_after(self.pages["id"], write)

    def test_another_tournaments_pages_stay_cached(self) -> None:
        other = Tournament.objects.create(event=create_event("Other Open"))
        url = f"/api/tournament?id={other.id}"
        self.client.get(url)
        with self.captureOnCommitCallbacks(execute=True):
            self.match.save()
        self.assertEqual(0, self.count_queries(url))

    def test_a_write_during_a_view_is_not_hidden(self) -> None:
        # The view's write lands after the version is read but before the page
        # is stored, so the stored page is already stale and must not be served.
        original = public_cache.PublicCacheMiddleware.__init__
        tid = str(self.tournament.id)

        def init(
            middleware: public_cache.PublicCacheMiddleware,
            get_response: Callable[[HttpRequest], HttpResponse],
        ) -> None:
            def writing_view(request: HttpRequest) -> HttpResponse:
                response = get_response(request)
                with self.captureOnCommitCallbacks(execute=True):
                    public_cache.bump(tid)
                return response

            original(middleware, writing_view)

        url = self.pages["id"]
        with patch.object(public_cache.PublicCacheMiddleware, "__init__", init):
            Client().get(url)  # Its own client, so self.client's views stay unpatched.
        self.assertGreater(self.count_queries(url), 0)

    def test_a_failing_lookup_never_fails_the_save(self) -> None:
        with (
            patch("server.public_cache.transaction.on_commit", side_effect=RuntimeError),
            self.assertLogs("server.public_cache", "WARNING"),
        ):
            self.match.save()


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
