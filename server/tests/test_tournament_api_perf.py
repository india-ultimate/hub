"""Public tournament endpoints: a constant number of queries, and no personal data."""

import datetime
from typing import Any

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from server.core.models import Player, UCPerson, User
from server.tests.base import ApiBaseTestCase
from server.tournament.models import (
    Bracket,
    CrossPool,
    Match,
    MatchEvent,
    MatchScore,
    MatchStats,
    Pool,
    PositionPool,
    SpiritScore,
    SwissRound,
    TournamentField,
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
        self.assertEqual({"id", "full_name"}, set(spirit["mvp_v2"]))
        self.assertEqual({"first_name", "last_name", "image_url"}, set(spirit["mvp"]))
        self.assertEqual(10, spirit["total"])
        suggested = match["suggested_score_team_1"]
        self.assertEqual(15, suggested["score_team_1"])
        self.assertEqual({"id", "full_name"}, set(suggested["entered_by"]))
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
        self.assertLess(self.count_queries(url), 4)

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
        self.assertEqual({"id", "full_name"}, set(event["scored_by"]))
        self.assertEqual(2, len(event["players"]))
        names = [p["full_name"] for p in event["players"]]
        self.assertEqual(sorted(names), names)

    def test_events_newest_first(self) -> None:
        self.add_event()
        self.add_event()
        times = [e["time"] for e in self.client.get(self.url).json()["events"]]
        self.assertEqual(sorted(times, reverse=True), times)
