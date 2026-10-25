import datetime
from typing import Any
from unittest import mock

from django.db import IntegrityError
from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Player, Team, User
from server.player_profile.slugs import has_base, unique_slug
from server.series.models import SeriesRegistration
from server.tests.base import create_event, create_player
from server.tests.test_eligibility import make_series
from server.tests.test_tournament_api_perf import TournamentApiTestCase
from server.tournament.models import (
    Match,
    MatchEvent,
    MatchStats,
    Registration,
    SpiritScore,
    Tournament,
)
from server.wrapped.models import PlayerWrapped


def make_player(first: str, last: str) -> Player:
    n = User.objects.count()
    user = User.objects.create(username=f"u{n}", first_name=first, last_name=last)
    return create_player(user)


class TestSlugs(TestCase):
    def test_slug_from_name(self) -> None:
        self.assertEqual(make_player("Ananya", "Rao").slug, "ananya-rao")

    def test_same_name_gets_suffix(self) -> None:
        slugs = [make_player("Ananya", "Rao").slug for _ in range(3)]
        self.assertEqual(slugs, ["ananya-rao", "ananya-rao-2", "ananya-rao-3"])

    def test_non_latin_name_falls_back(self) -> None:
        self.assertEqual(make_player("अनन्या", "").slug, "player")
        self.assertEqual(make_player("अनन्या", "").slug, "player-2")

    def test_rename_updates_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        player.user.first_name = "Anu"
        player.user.save()
        player.refresh_from_db()
        self.assertEqual(player.slug, "anu-rao")
        self.assertFalse(Player.objects.filter(slug="ananya-rao").exists())

    def test_rename_frees_old_slug_and_avoids_collision(self) -> None:
        a = make_player("Ananya", "Rao")
        b = make_player("Meera", "Iyer")
        b.user.first_name, b.user.last_name = "Ananya", "Rao"
        b.user.save()
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.slug, b.slug), ("ananya-rao", "ananya-rao-2"))

    def test_unrelated_save_keeps_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        with self.assertNumQueries(1):
            player.user.save(update_fields=["last_login"])
        player.refresh_from_db()
        self.assertEqual(player.slug, "ananya-rao")

    def test_unique_slug_pure(self) -> None:
        self.assertEqual(unique_slug("a", {"a", "a-2"}), "a-3")
        self.assertTrue(has_base("a-12", "a"))
        self.assertFalse(has_base("ab", "a"))

    def test_slug_collision_on_save_is_retried(self) -> None:
        make_player("Ananya", "Rao")
        stale = iter(["ananya-rao"])
        with mock.patch(
            "server.core.models.unique_slug",
            side_effect=lambda base, taken: next(stale, None) or unique_slug(base, taken),
        ):
            player = make_player("Ananya", "Rao")
        self.assertEqual(player.slug, "ananya-rao-2")

    def test_other_integrity_error_is_not_retried(self) -> None:
        first = make_player("Ananya", "Rao")
        first.iu_id = "X1"
        first.save()
        user = User.objects.create(username="dup", first_name="Ananya", last_name="Rao")
        with (
            mock.patch.object(Player, "assign_slug", autospec=True) as assign,
            self.assertRaises(IntegrityError),
        ):
            Player.objects.create(user=user, iu_id="X1", date_of_birth=first.date_of_birth)
        self.assertEqual(assign.call_count, 1)

    def test_save_with_update_fields_persists_new_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        player.slug = None
        player.save(update_fields=["imported_data"])
        player.refresh_from_db()
        self.assertEqual(player.slug, "ananya-rao")


class TestProfileApi(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.p = self.make_player()
        self.tournament.status = Tournament.Status.COMPLETED
        self.tournament.save()
        self.register(self.tournament, self.team_1)

    @property
    def url(self) -> str:
        return f"/api/player-profile/{self.p.slug}"

    def get(self) -> dict[str, Any]:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        result: dict[str, Any] = response.json()
        return result

    def register(self, tournament: Tournament, team: Team, role: str = "PLA") -> Registration:
        return Registration.objects.create(
            event=tournament.event, team=team, player=self.p, role=role
        )

    def make_tournament(self, status: str = "COM", days: int = 0) -> Tournament:
        self.n += 1
        event = create_event(f"Other {self.n}")
        event.start_date += datetime.timedelta(days=days)
        event.save()
        return Tournament.objects.create(event=event, status=status)

    def nominated(self, **fields: Player) -> SpiritScore:
        score = self.spirit()
        for field, player in fields.items():
            setattr(score, field, player)
        score.save()
        return score

    def match_in(self, tournament: Tournament, **scores: SpiritScore) -> Match:
        self.n += 1
        scores = {
            "spirit_score_team_1": self.spirit(),
            "spirit_score_team_2": self.spirit(),
            "self_spirit_score_team_1": self.spirit(),
            **scores,
        }
        return Match.objects.create(
            tournament=tournament,
            sequence_number=1,
            time=now() + datetime.timedelta(minutes=self.n),
            team_1=self.team_1,
            team_2=self.team_2,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
            **scores,
        )

    def stats_for(self, tournament: Tournament) -> list[MatchStats]:
        match = self.match_in(tournament)
        return [
            MatchStats.objects.create(
                match=match,
                tournament=tournament,
                initial_possession=self.team_1,
                current_possession=self.team_2,
            )
        ]

    def add_event(self, stats: MatchStats, kind: str, **fields: Any) -> MatchEvent:
        event = MatchEvent.objects.create(stats=stats, team=self.team_1, type=kind, **fields)
        event.players.add(self.p)
        return event

    def test_unknown_slug_404(self) -> None:
        response = self.client.get("/api/player-profile/nobody")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["message"], "Player not found")

    def test_logged_out_can_read(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_exact_keys(self) -> None:
        data = self.get()
        self.assertEqual(
            set(data),
            {
                "slug",
                "full_name",
                "profile_pic_url",
                "match_up",
                "state",
                "jersey_number",
                "current_team",
                "tournaments",
            },
        )
        self.assertEqual(
            set(data["tournaments"][0]),
            {
                "slug",
                "title",
                "start_date",
                "end_date",
                "location",
                "logo_light",
                "logo_dark",
                "status",
                "team",
                "role",
                "is_playing",
                "placement",
                "stats",
                "mvp",
                "msp",
            },
        )

    def test_no_personal_data(self) -> None:
        self.p.city = "Secretville"
        self.p.educational_institution = "Secret College"
        self.p.save()
        self.assert_no_personal_data(self.url)
        body = self.client.get(self.url).content.decode()
        self.assertNotIn("Secretville", body)
        self.assertNotIn("Secret College", body)

    def test_draft_tournament_hidden(self) -> None:
        draft = self.make_tournament(Tournament.Status.DRAFT)
        self.register(draft, self.team_2)
        slugs = [t["slug"] for t in self.get()["tournaments"]]
        self.assertEqual(slugs, [self.event.slug])

    def test_history_newest_first_with_team_and_role(self) -> None:
        newer = self.make_tournament(days=400)
        self.register(newer, self.team_2, role="CAP")
        data = self.get()
        self.assertEqual(
            [t["slug"] for t in data["tournaments"]], [newer.event.slug, self.event.slug]
        )
        self.assertEqual(data["tournaments"][0]["role"], "CAP")
        self.assertEqual(data["tournaments"][0]["team"]["id"], self.team_2.id)
        self.assertEqual(data["current_team"]["id"], self.team_2.id)

    def test_stats_counted(self) -> None:
        stats = self.stats_for(self.tournament)[0]
        self.add_event(stats, "SC", scored_by=self.p)
        self.add_event(stats, "SC", scored_by=self.p)
        self.add_event(stats, "SC", assisted_by=self.p)
        self.add_event(stats, "BL", block_by=self.p)
        other = self.stats_for(self.tournament)[0]
        self.add_event(other, "BL", block_by=self.p)
        self.add_event(other, "TA", throwaway_by=self.p)
        self.assertEqual(
            self.get()["tournaments"][0]["stats"],
            {"goals": 2, "assists": 1, "blocks": 2, "games": 2},
        )

    def test_game_counted_when_player_only_scored(self) -> None:
        stats = self.stats_for(self.tournament)[0]
        MatchEvent.objects.create(stats=stats, team=self.team_1, type="SC", scored_by=self.p)
        MatchEvent.objects.create(stats=stats, team=self.team_1, type="TA", throwaway_by=self.p)
        self.assertEqual(self.get()["tournaments"][0]["stats"]["games"], 1)

    def test_game_not_double_counted(self) -> None:
        stats = self.stats_for(self.tournament)[0]
        self.add_event(stats, "SC", scored_by=self.p)
        self.add_event(stats, "SC", scored_by=self.p, assisted_by=self.p)
        self.add_event(stats, "BL", block_by=self.p)
        self.assertEqual(self.get()["tournaments"][0]["stats"]["games"], 1)

    def test_game_with_no_appearance_counts_zero(self) -> None:
        stats = self.stats_for(self.tournament)[0]
        MatchEvent.objects.create(
            stats=stats, team=self.team_1, type="SC", scored_by=make_player("Other", "Person")
        )
        self.assertEqual(self.get()["tournaments"][0]["stats"]["games"], 0)

    def test_line_and_score_in_one_event_counts_one_game(self) -> None:
        stats = self.stats_for(self.tournament)[0]
        self.add_event(stats, "SC", scored_by=self.p)
        self.assertEqual(self.get()["tournaments"][0]["stats"]["games"], 1)

    def test_untracked_tournament_stats_none(self) -> None:
        self.assertIsNone(self.get()["tournaments"][0]["stats"])

    def test_tracked_but_zero_shows_zeros(self) -> None:
        self.stats_for(self.tournament)
        self.assertEqual(
            self.get()["tournaments"][0]["stats"],
            {"goals": 0, "assists": 0, "blocks": 0, "games": 0},
        )

    def test_unregistered_tournament_events_ignored(self) -> None:
        other = self.make_tournament()
        self.add_event(self.stats_for(other)[0], "SC", scored_by=self.p)
        self.assertEqual(len(self.get()["tournaments"]), 1)

    def test_mvp_msp_counted(self) -> None:
        self.match_in(
            self.tournament,
            spirit_score_team_1=self.nominated(mvp_v2=self.p, msp_v2=self.p),
            self_spirit_score_team_1=self.nominated(mvp_v2=self.p, msp_v2=self.p),
        )
        self.match_in(self.tournament, spirit_score_team_2=self.nominated(mvp_v2=self.p))
        row = self.get()["tournaments"][0]
        self.assertEqual((row["mvp"], row["msp"]), (2, 1))

    def test_placement_only_when_completed(self) -> None:
        self.tournament.current_seeding = {"1": self.team_2.id, "2": self.team_1.id}
        self.tournament.save()
        self.assertEqual(self.get()["tournaments"][0]["placement"], 2)
        self.tournament.current_seeding = {"1": self.team_2.id}
        self.tournament.save()
        self.assertIsNone(self.get()["tournaments"][0]["placement"])
        self.tournament.current_seeding = {"1": self.team_2.id, "2": self.team_1.id}
        self.tournament.status = Tournament.Status.LIVE
        self.tournament.save()
        self.assertIsNone(self.get()["tournaments"][0]["placement"])

    def test_queries_constant(self) -> None:
        def grow() -> None:
            for i in range(3):
                tournament = self.make_tournament(days=i + 1)
                self.register(tournament, self.team_1)
                stats = self.stats_for(tournament)[0]
                self.add_event(stats, "SC", scored_by=self.p)
                self.match_in(tournament, spirit_score_team_1=self.nominated(mvp_v2=self.p))

        self.assert_constant(self.url, grow)


class TestSlugsInPayloads(TournamentApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.p = self.make_player()

    def add_event(self, kind: str, **fields: Player) -> MatchEvent:
        stats = self.make_match().stats
        event = MatchEvent.objects.create(stats=stats, team=self.team_1, type=kind, **fields)
        event.players.add(self.p)
        return event

    def test_roster_has_slug(self) -> None:
        Registration.objects.create(
            event=self.tournament.event, team=self.team_1, player=self.p, role="PLA"
        )
        url = f"/api/v2/tournament/{self.tournament.event.slug}/team/{self.team_1.slug}/roster"
        (entry,) = self.client.get(url).json()
        self.assertEqual(entry["player"]["slug"], self.p.slug)

    def test_leaderboard_has_slug(self) -> None:
        self.add_event("SC", scored_by=self.p, assisted_by=self.p)
        self.add_event("BL", block_by=self.p)
        body = self.client.get(f"/api/tournament/{self.tournament.event.slug}/leaderboard").json()
        for key in ("scores", "assists", "blocks", "total"):
            self.assertEqual([row["slug"] for row in body[key]], [self.p.slug], key)

    def test_match_events_have_slug(self) -> None:
        event = self.add_event("SC", scored_by=self.p)
        response = self.client.get(f"/api/match/{event.stats.match_id}/stats")
        (got,) = response.json()["events"]
        self.assertEqual(got["scored_by"]["slug"], self.p.slug)
        self.assertEqual(got["players"][0]["slug"], self.p.slug)

    def test_series_roster_has_slug(self) -> None:
        series = make_series(None)
        SeriesRegistration.objects.create(series=series, team=self.team_1, player=self.p)
        response = self.client.get(f"/api/series/{series.slug}/team/{self.team_1.slug}/roster")
        (entry,) = response.json()
        self.assertEqual(entry["player"]["slug"], self.p.slug)

    def test_me_has_slug(self) -> None:
        self.login()
        player = self.client.get("/api/me").json()["player"]
        self.assertEqual(player["slug"], self.player.slug)

    def test_wrapped_teammate_slugs(self) -> None:
        q, r = self.make_player(), self.make_player()
        row = {"player_name": "x", "count": 3}
        PlayerWrapped.objects.create(
            player=self.player,
            year=2026,
            top_teammates_i_assisted=[{"player_id": q.id, **row}],
            top_teammates_who_assisted_me=[{"player_id": r.id, **row}],
        )
        self.login()
        body = self.client.get("/api/wrapped/2026").json()
        self.assertEqual(body["teammate_slugs"], {str(q.id): q.slug, str(r.id): r.slug})
