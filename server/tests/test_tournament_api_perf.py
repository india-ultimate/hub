"""Public tournament endpoints: a constant number of queries, and no personal data."""

import datetime
from typing import Any

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from server.core.models import CommentaryInfo, Player, Team, UCPerson, User
from server.series.models import Series, SeriesRegistration
from server.tests.base import ApiBaseTestCase, create_event
from server.tests.test_eligibility import make_series
from server.tournament.models import (
    Bracket,
    CrossPool,
    Event,
    Match,
    MatchEvent,
    MatchScore,
    MatchStats,
    Pool,
    PositionPool,
    Registration,
    SpiritScore,
    SwissRound,
    Tournament,
    TournamentField,
    UCRegistration,
)

SECRET_EMAIL = "secret-{}@example.com"
SECRET_PHONE = "+919812345678"
SECRET_DOB = "1987-06-05"
# Keys only personal data uses; none may appear in a public response.
PERSONAL_KEYS = ('"email"', '"phone"', '"date_of_birth"', '"guardian"')


class TournamentApiTestCase(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.n = 0
        self.person = UCPerson.objects.create(
            email="secret-uc@example.com", slug="uc", first_name="Old", last_name="Mvp"
        )
        stage: dict[str, Any] = {"tournament": self.tournament}
        self.pool = Pool.objects.create(
            **stage, sequence_number=1, name="A", initial_seeding={}, results={}
        )
        self.cross_pool = CrossPool.objects.create(**stage)
        self.bracket = Bracket.objects.create(
            **stage, sequence_number=1, name="1-8", initial_seeding={}, current_seeding={}
        )
        self.position_pool = PositionPool.objects.create(
            **stage, sequence_number=1, name="B", initial_seeding={}, results={}
        )
        self.swiss_round = SwissRound.objects.create(
            **stage, num_rounds=3, initial_seeding={}, results={}
        )
        self.team_1, self.team_2 = self.teams[0], self.teams[1]

    def make_player(self) -> Player:
        self.n += 1
        user = User.objects.create(
            username=f"player{self.n}@example.com",
            email=SECRET_EMAIL.format(self.n),
            phone=SECRET_PHONE,
            first_name=f"Player{self.n}",
            last_name="Public",
        )
        return Player.objects.create(user=user, date_of_birth=SECRET_DOB, gender="F")

    def spirit(self) -> SpiritScore:
        return SpiritScore.objects.create(
            rules=2,
            fouls=2,
            fair=2,
            positive=2,
            communication=2,
            total=10,
            mvp=self.person,
            msp=self.person,
            mvp_v2=self.make_player(),
            msp_v2=self.make_player(),
            comments="Great game",
        )

    def make_match(self) -> Match:
        """A played match with every nested object a match can have."""
        self.n += 1
        match = Match.objects.create(
            tournament=self.tournament,
            pool=self.pool,
            cross_pool=self.cross_pool,
            bracket=self.bracket,
            position_pool=self.position_pool,
            swiss_round=self.swiss_round,
            sequence_number=1,
            time=now() + datetime.timedelta(minutes=self.n),
            field=TournamentField.objects.create(tournament=self.tournament, name=f"F{self.n}"),
            team_1=self.team_1,
            team_2=self.team_2,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            suggested_score_team_1=MatchScore.objects.create(
                score_team_1=15, score_team_2=10, entered_by=self.make_player()
            ),
            suggested_score_team_2=MatchScore.objects.create(
                score_team_1=15, score_team_2=10, entered_by=self.make_player()
            ),
            spirit_score_team_1=self.spirit(),
            spirit_score_team_2=self.spirit(),
            self_spirit_score_team_1=self.spirit(),
            self_spirit_score_team_2=self.spirit(),
        )
        MatchStats.objects.create(
            match=match,
            tournament=self.tournament,
            initial_possession=self.team_1,
            current_possession=self.team_2,
        )
        return match

    def count_queries(self, url: str) -> int:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        return len(queries.captured_queries)

    def assert_constant(self, url: str, grow: Any) -> None:
        """The same number of queries before and after `grow()` adds rows."""
        before = self.count_queries(url)
        grow()
        self.assertEqual(before, self.count_queries(url))

    def assert_no_personal_data(self, url: str) -> None:
        body = self.client.get(url).content.decode()
        for secret in (SECRET_PHONE, SECRET_DOB, "secret-"):
            self.assertNotIn(secret, body)
        for key in PERSONAL_KEYS:
            self.assertNotIn(key, body)


class TestMatchLists(TournamentApiTestCase):
    def urls(self) -> list[str]:
        slug = self.tournament.event.slug
        return [
            f"/api/tournament/{self.tournament.id}/matches",
            f"/api/tournament/slug/{slug}/matches",
            f"/api/tournament/{slug}/team/{self.team_1.slug}/matches",
        ]

    def test_no_query_joins_too_many_tables(self) -> None:
        # Postgres spent 30 ms planning one 45-table join per request, on a
        # database with two shared CPUs; on a busy day that alone starved it.
        match = self.make_match()
        for url in [*self.urls(), f"/api/match/{match.id}"]:
            with CaptureQueriesContext(connection) as queries:
                self.client.get(url)
            joins = max(q["sql"].count(" JOIN ") for q in queries.captured_queries)
            self.assertLessEqual(joins, 20, url)

    def test_queries_dont_grow_with_matches(self) -> None:
        for _ in range(2):
            self.make_match()
        for url in self.urls():
            self.assert_constant(url, lambda: [self.make_match() for _ in range(5)])

    def test_no_personal_data(self) -> None:
        self.make_match()
        for url in self.urls():
            self.assert_no_personal_data(url)

    def test_sends_what_the_pages_read(self) -> None:
        self.make_match()
        (match,) = self.client.get(self.urls()[0]).json()
        team_keys = {"id", "name", "slug", "image", "image_url"}
        self.assertEqual(team_keys, set(match["team_1"]))
        self.assertEqual({"id", "name", "sequence_number"}, set(match["pool"]))
        self.assertEqual({"id"}, set(match["cross_pool"]))
        spirit = match["spirit_score_team_1"]
        self.assertEqual("Great game", spirit["comments"])
        self.assertEqual("Great game", match["self_spirit_score_team_2"]["comments"])
        self.assertEqual({"id", "full_name", "slug"}, set(spirit["mvp_v2"]))
        self.assertEqual({"id", "first_name", "last_name", "image_url"}, set(spirit["mvp"]))
        self.assertEqual(10, spirit["total"])
        suggested = match["suggested_score_team_1"]
        self.assertEqual(15, suggested["score_team_1"])
        self.assertEqual({"id", "full_name", "slug"}, set(suggested["entered_by"]))
        self.assertEqual(team_keys, set(match["stats"]["current_possession"]))
        self.assertTrue(match["field"]["name"].startswith("F"))

    def test_a_bare_match_has_nulls(self) -> None:
        Match.objects.create(
            tournament=self.tournament,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )
        (match,) = self.client.get(self.urls()[0]).json()
        for key in (
            "team_1",
            "pool",
            "cross_pool",
            "spirit_score_team_1",
            "suggested_score_team_1",
            "field",
            "stats",
        ):
            self.assertIsNone(match[key], key)

    def test_one_match(self) -> None:
        match = self.make_match()
        url = f"/api/match/{match.id}"
        self.assert_no_personal_data(url)
        self.assertEqual(self.team_1.slug, self.client.get(url).json()["team_1"]["slug"])
        # The match, then its four spirit scores with their people.
        self.assertEqual(5, self.count_queries(url))

    def test_unknown_match_keeps_its_message(self) -> None:
        response = self.client.get("/api/match/999999")
        self.assertEqual(400, response.status_code)
        self.assertEqual("Match does not exist", response.json()["message"])


class TestMatchStats(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.match = self.make_match()
        self.url = f"/api/match/{self.match.id}/stats"

    def add_event(self) -> None:
        event = MatchEvent.objects.create(
            stats=self.match.stats,
            team=self.team_1,
            started_on=MatchEvent.Mode.OFFENSE,
            type=MatchEvent.EventType.SCORE,
            scored_by=self.make_player(),
            assisted_by=self.make_player(),
            drop_by=self.make_player(),
            throwaway_by=self.make_player(),
            block_by=self.make_player(),
        )
        event.players.add(self.make_player(), self.make_player())

    def test_queries_dont_grow_with_events(self) -> None:
        self.add_event()
        self.add_event()

        def grow() -> None:
            for _ in range(5):
                self.add_event()

        self.assert_constant(self.url, grow)

    def test_no_personal_data(self) -> None:
        self.add_event()
        self.assert_no_personal_data(self.url)

    def test_sends_what_the_page_reads(self) -> None:
        self.add_event()
        stats = self.client.get(self.url).json()
        self.assertEqual(self.team_2.id, stats["current_possession"]["id"])
        (event,) = stats["events"]
        self.assertEqual(self.team_1.id, event["team"]["id"])
        self.assertEqual({"id", "full_name", "slug"}, set(event["scored_by"]))
        self.assertEqual(2, len(event["players"]))
        names = [p["full_name"] for p in event["players"]]
        self.assertEqual(sorted(names), names)

    def test_events_newest_first(self) -> None:
        self.add_event()
        self.add_event()
        times = [e["time"] for e in self.client.get(self.url).json()["events"]]
        self.assertEqual(sorted(times, reverse=True), times)


class TestRoster(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = f"/api/v2/tournament/{self.tournament.event.slug}/team/{self.team_1.slug}/roster"

    def add_player(self, jersey: int | None = 7) -> Player:
        player = self.make_player()
        Registration.objects.create(event=self.event, team=self.team_1, player=player)
        if jersey is not None:
            CommentaryInfo.objects.create(
                player=player,
                jersey_number=jersey,
                ultimate_origin="",
                ultimate_attraction="",
                ultimate_fav_role="",
                ultimate_fav_exp="",
                interests="",
                fun_fact="",
            )
        return player

    def test_queries_dont_grow_with_players(self) -> None:
        self.add_player()
        self.add_player(jersey=None)

        def grow() -> None:
            for _ in range(5):
                self.add_player()

        self.assert_constant(self.url, grow)

    def test_no_personal_data(self) -> None:
        self.add_player()
        self.assert_no_personal_data(self.url)

    def test_sends_what_the_page_reads(self) -> None:
        player = self.add_player(jersey=23)
        (entry,) = self.client.get(self.url).json()
        self.assertEqual(self.event.id, entry["event_id"])
        self.assertEqual(self.team_1.id, entry["team"]["id"])
        self.assertTrue(entry["is_playing"])
        self.assertIn("role", entry)
        self.assertEqual(
            {
                "id": player.id,
                "full_name": player.user.get_full_name(),
                "slug": player.slug,
                "profile_pic_url": None,
                "gender": "F",
                "commentary_info": {"jersey_number": 23},
            },
            entry["player"],
        )

    def test_a_player_without_commentary_info(self) -> None:
        self.add_player(jersey=None)
        (entry,) = self.client.get(self.url).json()
        self.assertIsNone(entry["player"]["commentary_info"])


class TestRosterPoints(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = f"/api/v2/tournament/{self.event.slug}/team/{self.team_1.slug}/roster-points"
        self.past = [create_event(f"Past {i}") for i in range(2)]
        before = self.event.start_date - datetime.timedelta(days=10)
        Event.objects.filter(pk__in=[e.pk for e in self.past]).update(
            start_date=before, end_date=before
        )

    def add_player(self, *points: int | None) -> None:
        player = self.make_player()
        Registration.objects.create(event=self.event, team=self.team_1, player=player)
        for event, score in zip(self.past, points, strict=False):
            Registration.objects.create(event=event, team=self.team_2, player=player, points=score)

    def test_averages_each_players_past_points_skipping_those_without(self) -> None:
        self.add_player(4, 6)
        self.add_player(8, None)
        self.add_player(0)
        self.add_player()
        self.assertEqual({"points": 6.5}, self.client.get(self.url).json())

    def test_queries_dont_grow_with_players(self) -> None:
        self.add_player(4, 6)

        def grow() -> None:
            for _ in range(5):
                self.add_player(3, 5)

        self.assert_constant(self.url, grow)


class TestSeriesLists(TournamentApiTestCase):
    def add_series(self) -> None:
        self.n += 1
        series = make_series(self.season)
        series.name = f"Series {self.n}"  # names are unique in a season
        series.save()
        series.teams.set(self.teams[:3])
        event = create_event(f"Series event {self.n}")
        event.series = series
        event.save()
        for team in self.teams[:2]:
            SeriesRegistration.objects.create(series=series, team=team, player=self.make_player())

    def test_queries_dont_grow_with_series(self) -> None:
        self.add_series()
        for url in ("/api/series/all", "/api/events"):
            self.assert_constant(url, self.add_series)

    def test_counts_each_teams_registrations(self) -> None:
        self.add_series()
        (series,) = self.client.get("/api/series/all").json()
        counts = {c["team_id"]: c["count"] for c in series["reg_count"]}
        self.assertEqual({self.teams[0].id: 1, self.teams[1].id: 1, self.teams[2].id: 0}, counts)


class TestTournaments(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.series = Series.objects.create(
            name="Nationals Series",
            type=Series.Type.MIXED,
            category=Series.Category.CLUB,
            start_date="2026-01-01",
            end_date="2026-12-31",
            series_roster_max_players=30,
            event_min_players_male=0,
            event_min_players_female=0,
            event_max_players_male=30,
            event_max_players_female=30,
        )

    def add_tournament(self) -> None:
        self.n += 1
        event = create_event(f"Event {self.n}")
        event.series = self.series
        event.save()
        tournament = Tournament.objects.create(event=event)
        team = Team.objects.create(name=f"Listed {self.n}")
        tournament.teams.add(team)
        tournament.partial_teams.add(team)
        self.series.teams.add(team)

    def add_team(self) -> None:
        self.n += 1
        team = Team.objects.create(name=f"Entered {self.n}")
        self.tournament.teams.add(team)
        self.tournament.partial_teams.add(team)
        team.admins.add(self.make_player().user)
        Registration.objects.create(event=self.event, team=team, player=self.make_player())

    def test_list_queries_dont_grow(self) -> None:
        def grow() -> None:
            for _ in range(5):
                self.add_tournament()

        self.add_tournament()
        self.assert_constant("/api/tournaments", grow)

    def test_list_keeps_what_managers_save(self) -> None:
        self.tournament.rules = "Be kind"
        self.tournament.initial_seeding = {"1": self.team_1.id}
        self.tournament.save()
        (tournament,) = (
            t for t in self.client.get("/api/tournaments").json() if t["id"] == self.tournament.id
        )
        self.assertEqual("Be kind", tournament["rules"])
        self.assertEqual({"1": self.team_1.id}, tournament["initial_seeding"])
        self.assertIn("current_seeding", tournament)
        self.assertIn(self.team_1.id, tournament["teams"])

    def test_list_series_has_no_teams(self) -> None:
        self.add_tournament()
        listed = [t for t in self.client.get("/api/tournaments").json() if t["event"]["series"]]
        series = listed[0]["event"]["series"]
        self.assertEqual("Nationals Series", series["name"])
        self.assertNotIn("teams", series)
        self.assertNotIn("reg_count", series)

    def test_one_tournament_queries_dont_grow_with_teams(self) -> None:
        def grow() -> None:
            for _ in range(5):
                self.add_team()

        self.event.series = self.series
        self.event.save()
        self.add_team()
        self.assert_constant(f"/api/tournament?slug={self.event.slug}", grow)

    def test_one_tournament_counts_registrations(self) -> None:
        self.add_team()
        team = self.tournament.teams.order_by("-id")[0]
        body = self.client.get(f"/api/tournament?slug={self.event.slug}").json()
        counts = {c["team_id"]: c["count"] for c in body["reg_count"]}
        self.assertEqual(1, counts[team.id])
        self.assertEqual(0, counts[self.teams[2].id])
        self.assertEqual({"id", "name", "slug", "image", "image_url"}, set(body["teams"][0]))

    def test_no_personal_data(self) -> None:
        self.add_team()
        self.assert_no_personal_data("/api/tournaments")
        self.assert_no_personal_data(f"/api/tournament?slug={self.event.slug}")

    def test_pools_dont_grow(self) -> None:
        def grow() -> None:
            for name in ("C", "D", "E"):
                Pool.objects.create(
                    tournament=self.tournament,
                    sequence_number=1,
                    name=name,
                    initial_seeding={},
                    results={},
                )

        self.assert_constant(f"/api/tournament/pools?id={self.tournament.id}", grow)

    def test_brackets_dont_grow(self) -> None:
        def grow() -> None:
            for name in ("9-12", "13-16", "17-20"):
                Bracket.objects.create(
                    tournament=self.tournament,
                    sequence_number=1,
                    name=name,
                    initial_seeding={},
                    current_seeding={},
                )

        self.assert_constant(f"/api/tournament/brackets?id={self.tournament.id}", grow)


class TestUCRoster(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.url = f"/api/v1/tournament/{self.event.slug}/team/{self.team_1.slug}/roster"
        self.team_1.admins.add(
            User.objects.create(username="uc-admin", email="secret-uc-admin@example.com")
        )
        for _ in range(2):
            self.register()

    def register(self) -> UCRegistration:
        player = self.make_player()
        person = UCPerson.objects.create(
            email=f"secret-uc-{self.n}@example.com",
            slug=f"uc-{self.n}",
            first_name=f"Uc{self.n}",
            last_name="Public",
            image_url="https://example.com/a.png",
        )
        player.ultimate_central_id = person.id
        player.save()
        return UCRegistration.objects.create(
            event=self.event, team=self.team_1, person=person, roles=["player", "captain"]
        )

    def test_no_personal_data(self) -> None:
        self.assert_no_personal_data(self.url)

    def test_queries_dont_grow_with_the_roster(self) -> None:
        self.assert_constant(self.url, lambda: [self.register() for _ in range(5)])

    def test_sends_what_the_pages_read(self) -> None:
        rows = self.client.get(self.url).json()
        row = next(r for r in rows if r["person"]["first_name"].startswith("Uc"))
        self.assertEqual(set(row), {"id", "roles", "team", "person"})
        self.assertEqual(row["roles"], ["player", "captain"])
        self.assertEqual(
            set(row["person"]), {"id", "first_name", "last_name", "image_url", "player"}
        )
        self.assertEqual(row["person"]["player"], {"gender": "F"})
        self.assertEqual(set(row["team"]), {"id", "name", "slug", "image", "image_url"})

    def test_person_without_a_player(self) -> None:
        person = UCPerson.objects.create(email="secret-x@example.com", slug="x", first_name="Z")
        UCRegistration.objects.create(
            event=self.event, team=self.team_1, person=person, roles=["coach"]
        )
        rows = self.client.get(self.url).json()
        self.assertIsNone(rows[-1]["person"]["player"])
        self.assertEqual(rows[-1]["person"]["first_name"], "Z")


class TestPlayerProfile(TournamentApiTestCase):
    def test_no_personal_data(self) -> None:
        player = self.make_player()
        Registration.objects.create(event=self.event, team=self.team_1, player=player)
        self.make_match()
        self.assert_no_personal_data(f"/api/player-profile/{player.slug}")
