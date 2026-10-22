import datetime
import json
from typing import Any
from unittest import mock

from server.core.models import Player, Team, User
from server.mcp.dispatch import ApiResponse
from server.series.models import Series
from server.tests.base import add_teams_to_event, create_event, create_pool, create_tournament
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tests.test_player_privacy import DOB, EMAIL, PHONE
from server.tournament.models import (
    Match,
    MatchEvent,
    MatchStats,
    SpiritScore,
    TournamentField,
)
from server.tournament.utils import start_tournament, update_tournament_spirit_rankings

SLUG = "nationals-2026"


class TournamentToolsTestCase(McpProtocolTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.event = create_event("Nationals 2026")
        self.event.slug = SLUG
        self.event.location = "Pune"
        self.event.series = Series.objects.create(
            name="Nationals Series",
            slug="nationals-series",
            start_date=self.event.start_date,
            end_date=self.event.end_date,
            type="MXD",
            category="Club",
            series_roster_max_players=20,
            event_min_players_male=1,
            event_min_players_female=1,
            event_max_players_male=10,
            event_max_players_female=10,
        )
        self.event.save()
        self.teams = add_teams_to_event(self.event, 4)
        self.tournament = create_tournament(self.event)
        create_pool("A", self.tournament, [1, 2, 3, 4])
        start_tournament(self.tournament)
        self.field = TournamentField.objects.create(name="Field 7", tournament=self.tournament)
        self.matches = list(Match.objects.filter(tournament=self.tournament).order_by("id"))
        self.first = self.matches[0]
        self.first.time = datetime.datetime(2026, 12, 1, 9, 30, tzinfo=datetime.UTC)
        self.first.field = self.field
        self.first.score_team_1, self.first.score_team_2 = 15, 11
        self.first.status = Match.Status.COMPLETED
        self.first.save()
        self.home = Team.objects.get(pk=self.tournament.initial_seeding["1"])
        self.away = Team.objects.get(pk=self.tournament.initial_seeding["2"])
        self.second = self.matches[1]
        self.second.time = datetime.datetime(2026, 12, 2, 9, 30, tzinfo=datetime.UTC)
        self.second.save()

    def data(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call(name, arguments)
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        return result["structuredContent"]

    def add_spirit(self, match: Match, total: int) -> None:
        spirit = SpiritScore.objects.create(
            rules=2, fouls=2, fair=2, positive=2, communication=2, total=total, comments="Secret"
        )
        match.spirit_score_team_1 = spirit
        match.self_spirit_score_team_1 = spirit
        match.spirit_score_team_2 = spirit
        match.self_spirit_score_team_2 = spirit
        match.save()
        update_tournament_spirit_rankings(self.tournament)


class TestToolsAreReadOnly(TournamentToolsTestCase):
    def test_all_three_say_so(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}

        for name in ("search", "get_tournament", "get_match"):
            self.assertTrue(listed[name]["annotations"]["readOnlyHint"], name)
            self.assertTrue(listed[name]["title"])


class TestSearch(TournamentToolsTestCase):
    def test_finds_teams_tournaments_and_series(self) -> None:
        data = self.data("search", {"query": "nationals"})
        self.assertEqual([], data["teams"])
        self.assertEqual(
            [
                {
                    "event_slug": SLUG,
                    "title": "Nationals 2026",
                    "start_date": str(self.event.start_date),
                }
            ],
            data["tournaments"],
        )
        self.assertEqual(
            [{"series_slug": "nationals-series", "name": "Nationals Series"}], data["series"]
        )

        teams = self.data("search", {"query": "team 2", "kind": "team"})["teams"]
        self.assertEqual(
            [{"team_id": self.teams[1].pk, "team_slug": self.teams[1].slug, "name": "Team 2"}],
            teams,
        )

    def test_words_match_in_any_order_and_with_words_between(self) -> None:
        self.assertEqual(
            "Nationals 2026",
            self.data("search", {"query": "2026 nationals"})["tournaments"][0]["title"],
        )
        found = self.data("search", {"query": "nationals zzz", "kind": "tournament"})
        self.assertEqual([], found["tournaments"])

    def test_kind_limits_the_search(self) -> None:
        data = self.data("search", {"query": "nationals", "kind": "series"})

        self.assertEqual({"series"}, set(data))

    def test_players_by_name_never_show_contact_details(self) -> None:
        owner = User.objects.create(
            username=EMAIL, email=EMAIL, phone=PHONE, first_name="Secret", last_name="Keeper"
        )
        player = Player.objects.create(user=owner, date_of_birth=DOB, city="Pune")

        response = self.modern(
            "tools/call", {"name": "search", "arguments": {"query": "Secret Keeper"}}
        )

        players = response.json()["result"]["structuredContent"]["players"]
        self.assertEqual([{"player_id": player.pk, "full_name": "Secret Keeper"}], players)
        for secret in (EMAIL, PHONE, DOB.isoformat()):
            self.assertNotIn(secret, response.content.decode())

    def test_a_query_is_stripped_before_its_length_counts(self) -> None:
        for query in ("  a ", "   "):
            result = self.modern(
                "tools/call", {"name": "search", "arguments": {"query": query}}
            ).json()["result"]

            self.assertTrue(result["isError"], query)
            self.assertEqual(
                "Search needs at least 2 letters", result["structuredContent"]["message"]
            )

    def test_a_long_query_is_refused(self) -> None:
        response = self.modern("tools/call", {"name": "search", "arguments": {"query": "a" * 101}})

        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("at most 100", result["structuredContent"]["message"])

    def fake_hub(self, per_year: int, calls: list[Any]) -> Any:
        def call(ctx: Any, method: str, path: str, query: Any = None) -> ApiResponse:
            year = (query or {}).get("year")
            calls.append(year)
            if path != "/api/tournaments/public":
                return ApiResponse(200, {"items": []})
            titles = [f"Straße Cup {year} {n}" for n in range(per_year)] if year else []
            cards = [{"event": {"title": t, "slug": t, "start_date": "2020-01-01"}} for t in titles]
            return ApiResponse(200, {"years": list(range(2026, 2016, -1)), "tournaments": cards})

        return call

    def test_tournament_search_scans_the_five_newest_years(self) -> None:
        calls: list[Any] = []
        with mock.patch("server.mcp.tools.tournaments.call_api", self.fake_hub(1, calls)):
            data = self.data("search", {"query": "STRASSE", "kind": "tournament"})

        self.assertEqual([None, 2026, 2025, 2024, 2023, 2022], calls)
        self.assertEqual(5, len(data["tournaments"]))

    def test_tournament_search_stops_at_the_limit(self) -> None:
        calls: list[Any] = []
        with mock.patch("server.mcp.tools.tournaments.call_api", self.fake_hub(6, calls)):
            data = self.data("search", {"query": "strasse", "kind": "tournament"})

        self.assertEqual([None, 2026, 2025], calls)
        self.assertEqual(10, len(data["tournaments"]))

    def test_short_query_is_refused(self) -> None:
        response = self.modern("tools/call", {"name": "search", "arguments": {"query": "a"}})

        self.assertTrue(response.json()["result"]["isError"])


class TestGetTournament(TournamentToolsTestCase):
    def test_overview(self) -> None:
        data = self.data("get_tournament", {"event_slug": SLUG})

        self.assertEqual(SLUG, data["event_slug"])
        self.assertEqual("Nationals 2026", data["title"])
        self.assertEqual("Pune", data["location"])
        self.assertEqual("Live", data["status"])
        self.assertEqual(str(self.event.start_date), data["start_date"])
        self.assertEqual(
            sorted(t.pk for t in self.teams), sorted(t["team_id"] for t in data["teams"])
        )
        self.assertEqual({"team_id", "team_slug", "name"}, set(data["teams"][0]))

    def test_schedule(self) -> None:
        data = self.data("get_tournament", {"event_slug": SLUG, "view": "schedule"})

        self.assertEqual(len(self.matches), len(data["matches"]))
        first = next(m for m in data["matches"] if m["match_id"] == self.first.pk)
        self.assertEqual("Field 7", first["field"])
        self.assertEqual(15, first["score_team_1"])
        self.assertEqual(11, first["score_team_2"])
        self.assertEqual(self.home.pk, first["team_1"]["team_id"])
        self.assertEqual("Completed", first["status"])
        self.assertTrue(first["time"].startswith("2026-12-01"))

    def test_schedule_for_one_team(self) -> None:
        team = self.home

        data = self.data(
            "get_tournament", {"event_slug": SLUG, "view": "schedule", "team_slug": team.slug}
        )

        self.assertEqual(3, len(data["matches"]))
        for match in data["matches"]:
            self.assertIn(team.pk, (match["team_1"]["team_id"], match["team_2"]["team_id"]))

    def test_schedule_for_one_day(self) -> None:
        data = self.data(
            "get_tournament", {"event_slug": SLUG, "view": "schedule", "day": "2026-12-02"}
        )

        self.assertEqual([self.second.pk], [m["match_id"] for m in data["matches"]])

    def test_unknown_team_is_reported(self) -> None:
        result = self.call(
            "get_tournament", {"event_slug": SLUG, "view": "schedule", "team_slug": "nope"}
        )

        self.assertTrue(result["isError"])
        self.assertIn("Team does not exist", result["structuredContent"]["message"])

    def test_unknown_tournament_with_a_team_is_reported_as_the_tournament(self) -> None:
        result = self.call(
            "get_tournament",
            {"event_slug": "no-such-event", "view": "schedule", "team_slug": self.home.slug},
        )

        self.assertTrue(result["isError"])
        self.assertIn(
            "No tournament with slug no-such-event", result["structuredContent"]["message"]
        )

    def test_standings(self) -> None:
        data = self.data("get_tournament", {"event_slug": SLUG, "view": "standings"})

        pool = data["pools"][0]
        self.assertEqual("A", pool["name"])
        self.assertEqual(4, len(pool["teams"]))
        expected = {"rank", "team_id", "team_slug", "name", "wins", "losses", "draws"}
        self.assertLessEqual(expected, set(pool["teams"][0]))
        self.assertEqual(4, len(data["current_seeding"]))

    def test_spirit(self) -> None:
        self.add_spirit(self.first, 10)

        data = self.data("get_tournament", {"event_slug": SLUG, "view": "spirit"})

        ranked = {r["team_id"]: r for r in data["teams"]}
        self.assertEqual(4, len(ranked))
        team = self.home
        self.assertEqual(10, ranked[team.pk]["points"])
        self.assertNotIn("Secret", json.dumps(data))

    def test_leaderboard(self) -> None:
        stats = MatchStats.objects.create(
            match=self.first,
            tournament=self.tournament,
            initial_possession=self.home,
            current_possession=self.home,
        )
        player = Player.objects.create(
            user=User.objects.create(username="s@x.com", first_name="Sia", last_name="Das"),
            date_of_birth=DOB,
        )
        MatchEvent.objects.create(
            stats=stats,
            team=self.home,
            started_on="OF",
            type="SC",
            scored_by=player,
        )

        data = self.data("get_tournament", {"event_slug": SLUG, "view": "leaderboard"})

        top = data["scores"][0]
        self.assertEqual(
            (player.pk, "Sia Das", 1), (top["player_id"], top["full_name"], top["scores"])
        )
        self.assertEqual([], data["assists"])

    def test_unknown_slug(self) -> None:
        for view in ("overview", "schedule", "standings", "spirit", "leaderboard"):
            result = self.call("get_tournament", {"event_slug": "nope", "view": view})

            self.assertTrue(result["isError"], view)
            self.assertIn("No tournament with slug nope", result["structuredContent"]["message"])

    def test_slug_is_not_a_path(self) -> None:
        result = self.call("get_tournament", {"event_slug": "../me"})

        self.assertTrue(result["isError"])
        self.assertIn("event_slug", result["structuredContent"]["message"])

    def test_long_schedule_is_cut_with_a_hint(self) -> None:
        template = self.matches[2]
        Match.objects.bulk_create(
            [
                Match(
                    tournament=self.tournament,
                    pool=template.pool,
                    team_1=template.team_1,
                    team_2=template.team_2,
                    sequence_number=1,
                    placeholder_seed_1=1,
                    placeholder_seed_2=2,
                    name="Round " + "x" * 10,
                )
                for _ in range(600)
            ]
        )

        response = self.modern(
            "tools/call",
            {"name": "get_tournament", "arguments": {"event_slug": SLUG, "view": "schedule"}},
        )
        data = response.json()["result"]["structuredContent"]

        self.assertLessEqual(len(response.content), 61_000)
        self.assertEqual(606, data["truncated"]["total"])
        self.assertEqual(len(data["matches"]), data["truncated"]["shown"])
        self.assertIn("Narrow with team_slug or day", data["truncated"]["hint"])


class TestGetMatch(TournamentToolsTestCase):
    def test_without_live_stats(self) -> None:
        self.add_spirit(self.first, 10)

        data = self.data("get_match", {"match_id": self.first.pk})

        self.assertEqual(self.first.pk, data["match_id"])
        self.assertEqual("Completed", data["status"])
        self.assertEqual("Field 7", data["field"])
        self.assertEqual((15, 11), (data["score_team_1"], data["score_team_2"]))
        self.assertEqual(self.home.pk, data["team_1"]["team_id"])
        self.assertFalse(data["has_live_stats"])
        self.assertIsNone(data["stats"])
        self.assertEqual(10, data["spirit"]["team_1"]["total"])
        self.assertNotIn("Secret", json.dumps(data))

    def test_with_live_stats(self) -> None:
        stats = MatchStats.objects.create(
            match=self.first,
            tournament=self.tournament,
            score_team_1=3,
            score_team_2=2,
            initial_possession=self.home,
            current_possession=self.away,
        )
        MatchEvent.objects.create(stats=stats, team=self.home, started_on="OF", type="SC")
        MatchEvent.objects.create(stats=stats, team=self.home, started_on="OF", type="TA")

        data = self.data("get_match", {"match_id": self.first.pk})

        self.assertTrue(data["has_live_stats"])
        self.assertEqual("First Half", data["stats"]["status"])
        self.assertEqual({"Score": 1, "Throwaway": 1}, data["stats"]["event_counts"])
        self.assertEqual((3, 2), (data["stats"]["score_team_1"], data["stats"]["score_team_2"]))

    def test_unknown_match(self) -> None:
        result = self.call("get_match", {"match_id": 999999})

        self.assertTrue(result["isError"])
        self.assertIn("No match with match_id 999999", result["structuredContent"]["message"])

    def test_match_id_must_be_a_number(self) -> None:
        result = self.call("get_match", {"match_id": "1/x"})

        self.assertTrue(result["isError"])
        self.assertIn("match_id", result["structuredContent"]["message"])
