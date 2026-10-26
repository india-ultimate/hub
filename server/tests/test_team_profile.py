import datetime
import json
from typing import Any
from unittest import mock

from django.utils.timezone import now

from server.core.models import Player, Team, User
from server.season.models import Season
from server.tests.base import create_event
from server.tests.test_tournament_api_perf import TournamentApiTestCase
from server.tournament.models import (
    Match,
    MatchEvent,
    MatchStats,
    Registration,
    SpiritScore,
    Tournament,
)
from server.utils import today


class TestTeamProfileApi(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.t = Team.objects.create(name="Subject", city="Pune", state_ut="MH", category="Club")
        self.rival = Team.objects.create(name="Rival")
        self.tournament.teams.add(self.t)
        self.tournament.status = Tournament.Status.COMPLETED
        self.tournament.save()

    def get(self, slug: str | None = None) -> dict[str, Any]:
        response = self.client.get(f"/api/team-profile/{slug or self.t.slug}")
        self.assertEqual(response.status_code, 200, response.content)
        result: dict[str, Any] = response.json()
        return result

    def make_tournament(self, status: str = "COM", days: int = 0, teams: bool = True) -> Tournament:
        self.n += 1
        event = create_event(f"Other {self.n}")
        event.start_date += datetime.timedelta(days=days)
        event.save()
        tournament = Tournament.objects.create(event=event, status=status)
        if teams:
            tournament.teams.add(self.t)
        return tournament

    def play(
        self,
        score: tuple[int, int],
        opponent: Team | None = None,
        tournament: Tournament | None = None,
        home: bool = True,
        status: str = "COM",
        minutes: int | None = None,
        **spirit: SpiritScore | None,
    ) -> Match:
        self.n += 1
        opponent = opponent or self.rival
        a, b = (self.t, opponent) if home else (opponent, self.t)
        return Match.objects.create(
            tournament=tournament or self.tournament,
            sequence_number=1,
            status=status,
            time=now() + datetime.timedelta(minutes=self.n if minutes is None else minutes),
            team_1=a,
            team_2=b,
            score_team_1=score[0] if home else score[1],
            score_team_2=score[1] if home else score[0],
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            **spirit,
        )

    def test_unknown_slug_404(self) -> None:
        response = self.client.get("/api/team-profile/nobody")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "Team not found")

    def test_duplicate_slug_takes_lowest_id(self) -> None:
        twin = Team.objects.create(name="Twin")
        Team.objects.filter(pk=twin.pk).update(slug=self.t.slug)
        self.assertEqual(self.get()["id"], self.t.id)

    def test_team_fields(self) -> None:
        self.t.admins.add(self.player.user)
        data = self.get()
        self.assertEqual(
            {k: data[k] for k in ("name", "category", "city", "state", "image", "image_url")},
            {
                "name": "Subject",
                "category": "Club",
                "city": "Pune",
                "state": "Maharashtra",
                "image": None,
                "image_url": None,
            },
        )
        self.assertEqual(
            data["admins"], [{"full_name": "John Williamson", "slug": self.player.slug}]
        )

    def test_admin_without_player_has_no_slug(self) -> None:
        self.t.admins.add(User.objects.create(username="x", first_name="No", last_name="Player"))
        self.assertEqual(self.get()["admins"], [{"full_name": "No Player", "slug": None}])

    def test_tournaments_newest_first_without_drafts(self) -> None:
        older = self.make_tournament(days=-50)
        newer = self.make_tournament(days=50)
        self.make_tournament(status="DFT", days=99)
        self.make_tournament(days=98, teams=False)
        slugs = [x["slug"] for x in self.get()["tournaments"]]
        self.assertEqual(slugs, [newer.event.slug, self.event.slug, older.event.slug])

    def test_bare_tournament_has_no_record(self) -> None:
        row = self.get()["tournaments"][0]
        self.assertIsNone(row["record"])
        self.assertEqual(row["division"], "Mixed")
        self.assertEqual(row["slug"], self.event.slug)

    def test_division_label(self) -> None:
        self.event.type = "WMN"
        self.event.save()
        self.assertEqual(self.get()["tournaments"][0]["division"], "Womens")

    def test_placement_and_spirit_rank_only_when_completed(self) -> None:
        self.tournament.current_seeding = {"1": self.rival.id, "2": self.t.id}
        self.tournament.spirit_ranking = [
            {"team_id": self.t.id, "rank": 3, "points": 9.5},
            {"team_id": self.rival.id, "rank": 1, "points": 12},
        ]
        self.tournament.save()
        row = self.get()["tournaments"][0]
        self.assertEqual((row["placement"], row["spirit_rank"]), (2, 3))
        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()
        row = self.get()["tournaments"][0]
        self.assertEqual((row["placement"], row["spirit_rank"]), (None, None))

    def test_non_numeric_seeding_key_gives_no_placement(self) -> None:
        self.tournament.current_seeding = {"x": self.t.id}
        self.tournament.save()
        self.assertIsNone(self.get()["tournaments"][0]["placement"])

    def test_record_counts_only_completed_with_both_teams(self) -> None:
        self.play((15, 10))
        self.play((9, 15), home=False)
        self.play((12, 12))
        self.play((15, 1), status="SCH")
        draft = self.make_tournament(status="DFT")
        self.play((15, 0), tournament=draft)
        half = self.play((15, 0))
        half.team_2 = None
        half.save()
        data = self.get()
        self.assertEqual(data["record"], {"played": 3, "wins": 1, "losses": 1, "draws": 1})
        self.assertEqual(data["tournaments"][0]["record"], {"wins": 1, "losses": 1, "draws": 1})

    def test_no_matches_no_record(self) -> None:
        data = self.get()
        self.assertIsNone(data["record"])
        self.assertIsNone(data["spirit"])
        self.assertEqual(data["form"], [])

    def test_spirit_is_mean_of_received_totals(self) -> None:
        def score(total: int) -> SpiritScore:
            s = self.spirit()
            s.total = total
            s.save()
            return s

        self.play((15, 10), spirit_score_team_1=score(10), spirit_score_team_2=score(1))
        self.play((15, 10), home=False, spirit_score_team_1=score(1), spirit_score_team_2=score(13))
        self.play((15, 10))
        self.assertEqual(self.get()["spirit"], 11.5)

    def test_form_newest_first_max_five_from_this_side(self) -> None:
        for i in range(6):
            self.play((10 + i, 5), minutes=i * 10 + 1000)
        self.play((3, 9), home=False, minutes=5000)
        form = self.get()["form"]
        self.assertEqual(len(form), 5)
        self.assertEqual(
            (form[0]["result"], form[0]["score_for"], form[0]["score_against"]), ("L", 3, 9)
        )
        self.assertEqual(form[1]["score_for"], 15)
        self.assertEqual(form[0]["opponent"]["id"], self.rival.id)
        self.assertEqual(form[0]["tournament_slug"], self.event.slug)
        self.assertEqual(form[0]["tournament_title"], self.event.title)

    def test_form_date_in_ist_else_event_start(self) -> None:
        match = self.play((15, 10))
        Match.objects.filter(pk=match.pk).update(
            time=datetime.datetime(2026, 3, 1, 20, 0, tzinfo=datetime.UTC)
        )
        self.assertEqual(self.get()["form"][0]["date"], "2026-03-02")
        Match.objects.filter(pk=match.pk).update(time=None)
        self.assertEqual(self.get()["form"][0]["date"], self.event.start_date.isoformat())

    def test_rivals(self) -> None:
        a = Team.objects.create(name="Alpha")
        b = Team.objects.create(name="Beta")
        once = Team.objects.create(name="Once")
        for _ in range(2):
            self.play((15, 10), opponent=b)
            self.play((15, 10), opponent=a, home=False)
        self.play((5, 10), opponent=a)
        self.play((5, 10), opponent=once)
        self.play((15, 10), opponent=self.rival)
        self.play((5, 10), opponent=self.rival)
        rivals = self.get()["rivals"]
        self.assertEqual(
            [(r["team"]["name"], r["played"], r["wins"], r["losses"]) for r in rivals],
            [("Alpha", 3, 2, 1), ("Beta", 2, 2, 0), ("Rival", 2, 1, 1)],
        )

    def test_rivals_max_five(self) -> None:
        for i in range(7):
            other = Team.objects.create(name=f"R{i}")
            self.play((1, 0), opponent=other)
            self.play((1, 0), opponent=other)
        self.assertEqual(len(self.get()["rivals"]), 5)

    def current_season(self) -> Season:
        return Season.objects.get(pk=Season.containing(today()).pk)  # type: ignore[union-attr]

    def register(self, tournament: Tournament, name: str, role: str) -> Registration:
        self.n += 1
        user = User.objects.create(username=f"r{self.n}", first_name=name, last_name="Z")
        player = Player.objects.create(user=user, date_of_birth="2000-01-01")
        return Registration.objects.create(
            event=tournament.event, team=self.t, player=player, role=role
        )

    def in_season(self, tournament: Tournament, offset: int = 0) -> None:
        tournament.event.start_date = today() + datetime.timedelta(days=offset)
        tournament.event.save()

    def test_no_roster_without_season_or_registrations(self) -> None:
        self.assertIsNone(self.get()["roster"])
        t = self.make_tournament()
        self.register(t, "P", "DFLT")
        with mock.patch.object(Season, "containing", return_value=None):
            self.assertIsNone(self.get()["roster"])
        self.in_season(t)
        self.assertIsNotNone(self.get()["roster"])

    def test_roster_ordered_by_role_then_name(self) -> None:
        season = self.current_season()
        t = self.make_tournament()
        self.in_season(t, 2)
        for name, role in [
            ("Zed", "DFLT"),
            ("Amy", "DFLT"),
            ("Mia", "MNGR"),
            ("Coa", "COACH"),
            ("Ace", "ACOACH"),
            ("Spi", "SCAP"),
            ("Cap", "CAP"),
        ]:
            self.register(t, name, role)
        roster = self.get()["roster"]
        self.assertEqual(roster["season"], season.label)
        self.assertEqual(roster["tournament_slug"], t.event.slug)
        self.assertEqual(
            [(p["full_name"], p["role"]) for p in roster["players"]],
            [
                ("Cap Z", "CAP"),
                ("Spi Z", "SCAP"),
                ("Amy Z", "DFLT"),
                ("Zed Z", "DFLT"),
                ("Coa Z", "COACH"),
                ("Ace Z", "ACOACH"),
                ("Mia Z", "MNGR"),
            ],
        )

    def test_roster_uses_newest_non_draft_tournament_in_season(self) -> None:
        self.current_season()
        old = self.make_tournament()
        self.in_season(old, -3)
        new = self.make_tournament()
        self.in_season(new, 3)
        draft = self.make_tournament(status="DFT")
        self.in_season(draft, 4)
        outside = self.make_tournament()
        self.in_season(outside, 900)
        for t in (old, new, draft, outside):
            self.register(t, "P", "DFLT")
        self.assertEqual(self.get()["roster"]["tournament_slug"], new.event.slug)

    def stats(self, match: Match) -> MatchStats:
        return MatchStats.objects.create(
            match=match,
            tournament=match.tournament,
            initial_possession=self.t,
            current_possession=self.rival,
        )

    def add_event(
        self, stats: MatchStats, kind: str, team: Team | None = None, **who: Player | None
    ) -> None:
        MatchEvent.objects.create(stats=stats, team=team or self.t, type=kind, **who)

    def named(self, first: str) -> Player:
        self.n += 1
        user = User.objects.create(username=f"n{self.n}", first_name=first, last_name="L")
        return Player.objects.create(user=user, date_of_birth="2000-01-01")

    def test_leaders(self) -> None:
        amy, bob, cat, dan, eve = (self.named(n) for n in ("Amy", "Bob", "Cat", "Dan", "Eve"))
        stats = self.stats(self.play((15, 10)))
        for scorer, assister, times in [(amy, bob, 3), (cat, amy, 3), (bob, cat, 1), (dan, eve, 1)]:
            for _ in range(times):
                self.add_event(stats, "SC", scored_by=scorer, assisted_by=assister)
        self.add_event(stats, "BL", block_by=eve)
        self.add_event(stats, "SC", team=self.rival, scored_by=eve, assisted_by=eve)
        self.add_event(stats, "SC", scored_by=None)
        leaders = self.get()["leaders"]
        goals = [(x["player"]["full_name"], x["value"]) for x in leaders["goals"]]
        self.assertEqual(goals, [("Amy L", 3), ("Cat L", 3), ("Bob L", 1)])
        assists = [(x["player"]["full_name"], x["value"]) for x in leaders["assists"]]
        self.assertEqual(assists, [("Amy L", 3), ("Bob L", 3), ("Cat L", 1)])
        self.assertEqual(
            [(x["player"]["slug"], x["value"]) for x in leaders["blocks"]], [(eve.slug, 1)]
        )
        self.assertEqual(leaders["mvp"], [])

    def test_leaders_ignore_draft_tournaments(self) -> None:
        draft = self.make_tournament(status="DFT")
        stats = self.stats(self.play((15, 10), tournament=draft))
        self.add_event(stats, "SC", scored_by=self.named("Amy"))
        self.assertEqual(self.get()["leaders"]["goals"], [])

    def test_mvp_msp_come_from_this_sides_received_scores(self) -> None:
        ours, theirs = self.named("Ours"), self.named("Theirs")

        def nominated(mvp: Player, msp: Player) -> SpiritScore:
            s = self.spirit()
            s.mvp_v2, s.msp_v2 = mvp, msp
            s.save()
            return s

        self.play(
            (15, 10),
            spirit_score_team_1=nominated(ours, ours),
            spirit_score_team_2=nominated(theirs, theirs),
        )
        self.play(
            (15, 10),
            home=False,
            spirit_score_team_1=nominated(theirs, theirs),
            spirit_score_team_2=nominated(ours, ours),
        )
        leaders = self.get()["leaders"]
        for key in ("mvp", "msp"):
            self.assertEqual(
                [(x["player"]["slug"], x["value"]) for x in leaders[key]], [(ours.slug, 2)]
            )

    def test_leader_with_deleted_player_is_skipped(self) -> None:
        gone = self.named("Gone")
        s = self.spirit()
        s.mvp_v2 = gone
        s.save()
        self.play((15, 10), spirit_score_team_1=s)
        gone.delete()
        self.assertEqual(self.get()["leaders"]["mvp"], [])

    def test_no_personal_data(self) -> None:
        self.t.admins.add(self.make_player().user)
        self.register(self.tournament, "Pii", "CAP")
        self.play((15, 10), spirit_score_team_1=self.spirit(), spirit_score_team_2=self.spirit())
        self.assert_no_personal_data(f"/api/team-profile/{self.t.slug}")
        body = json.dumps(self.get())
        self.assertNotIn("player1@example.com", body)
        self.assertNotIn("username", body)

    def test_queries_dont_grow(self) -> None:
        self.current_season()
        url = f"/api/team-profile/{self.t.slug}"
        self.in_season(self.tournament)
        self.register(self.tournament, "A", "CAP")
        stats = self.stats(self.play((15, 10), spirit_score_team_1=self.spirit()))
        self.add_event(stats, "SC", scored_by=self.named("S"), assisted_by=self.named("T"))

        def grow() -> None:
            for _ in range(3):
                other = Team.objects.create(name=f"Other {self.n}")
                t = self.make_tournament()
                self.register(t, "B", "DFLT")
                for _ in range(2):
                    s = self.stats(
                        self.play(
                            (15, 10),
                            opponent=other,
                            tournament=t,
                            spirit_score_team_2=self.spirit(),
                        )
                    )
                    self.add_event(s, "BL", block_by=self.named("Blk"))

        self.assert_constant(url, grow)

    def test_slugless_player_and_case_insensitive_ties(self) -> None:
        lower, upper = self.named("bob"), self.named("Zed")
        Player.objects.filter(pk=lower.pk).update(slug=None)
        stats = self.stats(self.play((15, 10)))
        for p in (upper, lower):
            self.add_event(stats, "SC", scored_by=p)
        goals = self.get()["leaders"]["goals"]
        self.assertEqual([x["player"]["slug"] for x in goals], [None, upper.slug])
