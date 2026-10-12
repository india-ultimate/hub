"""Every write a public page shows refreshes that page."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from django.db.models import Model

from server.core.models import Team
from server.tests.base import create_event
from server.tests.test_cache_store import CacheTestCase
from server.tournament.models import Match, MatchEvent, Registration, Tournament


def saving(row: Model | None) -> Callable[[], None]:
    assert row is not None  # noqa: S101 - make_match fills every relation
    return row.save


class TestCacheInvalidation(CacheTestCase):
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

    def test_a_failing_lookup_never_fails_the_save(self) -> None:
        with (
            patch("server.cache.store.transaction.on_commit", side_effect=RuntimeError),
            self.assertLogs("server.cache", "WARNING"),
        ):
            self.match.save()
