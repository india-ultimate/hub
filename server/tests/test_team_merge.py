import datetime
from typing import Any
from unittest import mock

from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase, override_settings

from server.core.models import Player, Team, User
from server.duplicates.teams.merge import (
    TeamMergeBlockedError,
    blockers,
    compare,
    default_keeper,
    merge_teams,
)
from server.duplicates.teams.models import TeamMerge
from server.registration.models import RosterEntry, RosterSwap
from server.series.models import Series, SeriesRegistration, SeriesRosterInvitation
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.tests.base import create_event, create_player
from server.tournament.models import (
    Bracket,
    EventRosterInvitation,
    Match,
    MatchEvent,
    MatchStats,
    Pool,
    Registration,
    SwissRound,
    Tournament,
)
from server.transaction.models import RazorpayTransaction
from server.wrapped.models import PlayerWrapped

# The admin's templates need static files, and tests have no manifest.
STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def make_series(name: str) -> Series:
    return Series.objects.create(
        name=name,
        start_date=datetime.date(2026, 1, 1),
        end_date=datetime.date(2026, 12, 31),
        type="MXD",
        category="Club",
        series_roster_max_players=20,
        event_min_players_male=1,
        event_min_players_female=1,
        event_max_players_male=10,
        event_max_players_female=10,
    )


class TeamMergeTestCase(TestCase):
    def setUp(self) -> None:
        self.keeper = Team.objects.create(name="Goosebumps")
        self.dup = Team.objects.create(name="Goosebumps ", city="Pune", ultimate_central_id=212436)
        self.rival = Team.objects.create(name="Rivals")
        self.user = User.objects.create(username="p@x.com", email="p@x.com")
        self.player = create_player(self.user)

    def tournament_with(self, *teams: Team, title: str = "Nationals") -> Tournament:
        tournament = Tournament.objects.create(event=create_event(title))
        tournament.teams.add(*teams)
        tournament.refresh_from_db()
        return tournament


class TestMergeMovesEverything(TeamMergeTestCase):
    def test_rows_follow_the_kept_team_and_the_copy_is_deleted(self) -> None:
        tournament = self.tournament_with(self.rival, self.dup)
        event = tournament.event
        Registration.objects.create(event=event, team=self.dup, player=self.player)
        RosterEntry.objects.create(event=event, team=self.dup, player=self.player)
        match = Match.objects.create(
            tournament=tournament,
            team_1=self.dup,
            team_2=self.rival,
            sequence_number=1,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )
        stats = MatchStats.objects.create(
            match=match,
            tournament=tournament,
            initial_possession=self.dup,
            current_possession=self.dup,
        )
        MatchEvent.objects.create(stats=stats, team=self.dup, type="SC", started_on="OFF")
        order = RazorpayTransaction.objects.create(
            user=self.user, amount=100, order_id="order_1", team=self.dup
        )
        series = make_series("Club Series")
        series.teams.add(self.dup)
        SeriesRegistration.objects.create(series=series, team=self.dup, player=self.player)
        admin = User.objects.create(username="a@x.com", email="a@x.com")
        self.dup.admins.add(admin)
        self.keeper.admins.add(self.user)
        # Linked to both copies: one link must survive, not two, not zero.
        self.player.teams.add(self.keeper, self.dup)

        merge_teams(self.keeper, [self.dup])

        self.assertFalse(Team.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(Registration.objects.get().team, self.keeper)
        self.assertEqual(RosterEntry.objects.get().team, self.keeper)
        match.refresh_from_db()
        stats.refresh_from_db()
        self.assertEqual(match.team_1, self.keeper)
        self.assertEqual(stats.initial_possession, self.keeper)
        self.assertEqual(stats.current_possession, self.keeper)
        self.assertEqual(MatchEvent.objects.get().team, self.keeper)
        order.refresh_from_db()
        self.assertEqual(order.team, self.keeper)
        self.assertEqual(list(series.teams.all()), [self.keeper])
        self.assertEqual(SeriesRegistration.objects.get().team, self.keeper)
        self.assertEqual(set(self.keeper.admins.all()), {self.user, admin})
        self.assertEqual(list(Player.objects.get().teams.all()), [self.keeper])
        self.assertEqual(set(tournament.teams.all()), {self.rival, self.keeper})

    def test_every_way_a_player_is_tied_to_the_copy_moves_to_the_keeper(self) -> None:
        event = create_event("Regionals")
        series = make_series("Club Series")
        other = create_player(User.objects.create(username="q@x.com", email="q@x.com"))
        rows = [
            Registration.objects.create(event=event, team=self.dup, player=self.player),
            SeriesRegistration.objects.create(series=series, team=self.dup, player=self.player),
            RosterEntry.objects.create(event=event, team=self.dup, player=other),
            RosterSwap.objects.create(
                event=event, team=self.dup, out_player=other, in_player=self.player
            ),
            EventRosterInvitation.objects.create(
                event=event, from_user=self.user, to_player=other, team=self.dup
            ),
            SeriesRosterInvitation.objects.create(
                series=series, from_user=self.user, to_player=other, team=self.dup
            ),
        ]
        self.player.teams.add(self.dup)
        other.teams.add(self.dup)

        merge_teams(self.keeper, [self.dup])

        for row in rows:
            row.refresh_from_db()
            self.assertEqual(row.team_id, self.keeper.pk, type(row).__name__)  # type: ignore[attr-defined]
        for player in (self.player, other):
            self.assertEqual(list(player.teams.all()), [self.keeper])

    def test_wrapped_lists_the_kept_team_once(self) -> None:
        wrapped = PlayerWrapped.objects.create(
            player=self.player,
            year=2025,
            teams_played_for=[
                {"team_name": "Goosebumps", "team_id": self.keeper.pk, "tournament_count": 2},
                {"team_name": "Goosebumps ", "team_id": self.dup.pk, "tournament_count": 3},
                {"team_name": "Rivals", "team_id": self.rival.pk, "tournament_count": 1},
            ],
        )
        only_copy = PlayerWrapped.objects.create(
            player=self.player,
            year=2024,
            teams_played_for=[
                {"team_name": "Goosebumps ", "team_id": self.dup.pk, "tournament_count": 1}
            ],
        )

        merge_teams(self.keeper, [self.dup])

        wrapped.refresh_from_db()
        only_copy.refresh_from_db()
        kept = {"team_name": "Goosebumps", "team_id": self.keeper.pk}
        self.assertEqual(
            wrapped.teams_played_for,
            [
                {**kept, "tournament_count": 5},
                {"team_name": "Rivals", "team_id": self.rival.pk, "tournament_count": 1},
            ],
        )
        self.assertEqual(only_copy.teams_played_for, [{**kept, "tournament_count": 1}])

    def test_details_the_kept_team_lacks_are_filled_from_the_copy(self) -> None:
        self.keeper.city = "Mumbai"
        self.keeper.save()

        merge_teams(self.keeper, [self.dup])

        self.keeper.refresh_from_db()
        self.assertEqual(self.keeper.name, "Goosebumps")
        self.assertEqual(self.keeper.city, "Mumbai")
        self.assertEqual(self.keeper.ultimate_central_id, 212436)

    def test_the_kept_team_keeps_its_own_logo_by_default(self) -> None:
        Team.objects.filter(pk=self.keeper.pk).update(image_url="https://x.com/kept.png")
        Team.objects.filter(pk=self.dup.pk).update(image="team_logos/copy.png")

        merge_teams(self.keeper, [self.dup])

        self.keeper.refresh_from_db()
        # Not the copy's file, which would show over the kept team's URL.
        self.assertEqual(
            (self.keeper.image.name, self.keeper.image_url), ("", "https://x.com/kept.png")
        )

    def test_the_logo_can_come_from_a_copy(self) -> None:
        Team.objects.filter(pk=self.keeper.pk).update(image="team_logos/kept.png")
        Team.objects.filter(pk=self.dup.pk).update(image_url="https://x.com/copy.png")

        merge_teams(self.keeper, [self.dup], logo=self.dup)

        self.keeper.refresh_from_db()
        self.assertEqual(
            (self.keeper.image.name, self.keeper.image_url), ("", "https://x.com/copy.png")
        )

    def test_the_merge_is_recorded_with_what_was_deleted(self) -> None:
        actor = User.objects.create(username="staff@x.com", email="staff@x.com")
        Registration.objects.create(
            event=create_event("Regionals"), team=self.dup, player=self.player
        )

        merge = merge_teams(self.keeper, [self.dup], actor=actor)

        self.assertEqual(TeamMerge.objects.get(), merge)
        self.assertEqual(merge.keeper, self.keeper)
        self.assertEqual(merge.merged_by, actor)
        self.assertEqual(merge.absorbed_team_ids, [self.dup.pk])
        self.assertEqual(merge.moved["server.Registration.team"], 1)
        (row,) = merge.snapshot
        self.assertEqual(row["pk"], self.dup.pk)
        self.assertEqual(row["fields"]["name"], "Goosebumps ")

    def test_several_copies_fold_into_one(self) -> None:
        third = Team.objects.create(name="goosebumps")
        self.player.teams.add(self.dup, third)

        merge_teams(self.keeper, [self.dup, third])

        self.assertEqual(Team.objects.filter(name__icontains="goosebumps").count(), 1)
        self.assertEqual(list(self.player.teams.all()), [self.keeper])


class TestTournamentsReadTheSame(TeamMergeTestCase):
    def test_seeding_keeps_its_order(self) -> None:
        tournament = self.tournament_with(self.rival, self.dup)
        Tournament.objects.filter(pk=tournament.pk).update(
            initial_seeding={"1": self.rival.pk, "2": self.dup.pk},
            current_seeding={"1": self.dup.pk, "2": self.rival.pk},
            spirit_ranking=[{"team_id": self.dup.pk, "points": 12.5, "rank": 1}],
        )

        merge_teams(self.keeper, [self.dup])

        tournament.refresh_from_db()
        self.assertEqual(tournament.initial_seeding, {"1": self.rival.pk, "2": self.keeper.pk})
        self.assertEqual(tournament.current_seeding, {"1": self.keeper.pk, "2": self.rival.pk})
        self.assertEqual(
            tournament.spirit_ranking, [{"team_id": self.keeper.pk, "points": 12.5, "rank": 1}]
        )

    def test_stage_tables_point_at_the_kept_team(self) -> None:
        tournament = self.tournament_with(self.rival, self.dup)
        d, r, k = str(self.dup.pk), str(self.rival.pk), self.keeper.pk
        # GF equal to the copy's id: a number that happens to match must stay.
        row = {"rank": 1, "wins": 1, "GF": self.dup.pk, "id": self.dup.pk}
        other = {"rank": 2, "wins": 0, "GF": 3, "id": self.rival.pk}
        Pool.objects.create(
            sequence_number=1,
            name="A",
            tournament=tournament,
            initial_seeding={"1": self.dup.pk, "2": self.rival.pk},
            results={d: row, r: other},
        )
        SwissRound.objects.create(
            tournament=tournament,
            num_rounds=3,
            initial_seeding={"1": self.dup.pk, "2": self.rival.pk},
            results={d: row, r: other},
            round_results={"1": {d: row, r: other}},
            byes={"1": self.dup.pk},
        )
        Bracket.objects.create(
            sequence_number=1,
            tournament=tournament,
            initial_seeding={"1": self.dup.pk},
            current_seeding={"1": self.dup.pk},
        )

        merge_teams(self.keeper, [self.dup])

        moved = {**row, "id": k}
        pool = Pool.objects.get()
        self.assertEqual(pool.initial_seeding, {"1": k, "2": self.rival.pk})
        self.assertEqual(pool.results, {str(k): moved, r: other})
        swiss = SwissRound.objects.get()
        self.assertEqual(swiss.initial_seeding, {"1": k, "2": self.rival.pk})
        self.assertEqual(swiss.results, {str(k): moved, r: other})
        self.assertEqual(swiss.round_results, {"1": {str(k): moved, r: other}})
        self.assertEqual(swiss.byes, {"1": k})
        bracket = Bracket.objects.get()
        self.assertEqual(bracket.initial_seeding, {"1": k})
        self.assertEqual(bracket.current_seeding, {"1": k})

    def test_an_id_left_only_in_json_is_rewritten_too(self) -> None:
        # The team was taken off the tournament, but its standings remain.
        elsewhere = self.tournament_with(self.rival, title="Elsewhere")
        Tournament.objects.filter(pk=elsewhere.pk).update(current_seeding={"1": self.dup.pk})
        untouched = self.tournament_with(self.rival, title="Untouched")

        merge_teams(self.keeper, [self.dup])

        elsewhere.refresh_from_db()
        self.assertEqual(elsewhere.current_seeding, {"1": self.keeper.pk})
        untouched.refresh_from_db()
        self.assertEqual(untouched.current_seeding, {"1": self.rival.pk})

    def test_the_public_pages_are_refreshed(self) -> None:
        tournament = self.tournament_with(self.rival, self.dup)
        with mock.patch("server.duplicates.teams.merge.store.bump") as bump:
            merge_teams(self.keeper, [self.dup])
        bump.assert_any_call(str(tournament.pk))


class TestBlockers(TeamMergeTestCase):
    def test_teams_at_one_event_cannot_be_merged(self) -> None:
        self.tournament_with(self.keeper, self.dup, title="Nationals 2025")

        self.assertEqual(
            blockers([self.keeper, self.dup]),
            [
                f"Goosebumps #{self.keeper.pk} and Goosebumps #{self.dup.pk} were both at Nationals 2025"
            ],
        )
        with self.assertRaises(TeamMergeBlockedError):
            merge_teams(self.keeper, [self.dup])
        self.assertTrue(Team.objects.filter(pk=self.dup.pk).exists())

    def test_standings_naming_both_teams_count_too(self) -> None:
        tournament = self.tournament_with(self.rival, title="Old Nationals")
        Tournament.objects.filter(pk=tournament.pk).update(
            current_seeding={"1": self.keeper.pk, "2": self.dup.pk}
        )

        self.assertEqual(len(blockers([self.keeper, self.dup])), 1)

    def test_rostered_at_one_event_counts_too(self) -> None:
        event = create_event("Regionals")
        Registration.objects.create(event=event, team=self.keeper, player=self.player)
        other = create_player(User.objects.create(username="q@x.com", email="q@x.com"))
        RosterEntry.objects.create(event=event, team=self.dup, player=other)

        self.assertEqual(len(blockers([self.keeper, self.dup])), 1)

    def test_teams_in_one_series_cannot_be_merged(self) -> None:
        series = make_series("Club Series")
        series.teams.add(self.keeper)
        SeriesRegistration.objects.create(series=series, team=self.dup, player=self.player)

        self.assertEqual(
            blockers([self.keeper, self.dup]),
            [
                f"Goosebumps #{self.keeper.pk} and Goosebumps #{self.dup.pk} were both in Club Series"
            ],
        )

    def test_any_pair_counts_not_just_the_keeper(self) -> None:
        third = Team.objects.create(name="Goosebumps B")
        self.tournament_with(self.dup, third, title="Nationals 2025")

        with self.assertRaises(TeamMergeBlockedError):
            merge_teams(self.keeper, [self.dup, third])

    def test_unrelated_teams_have_no_blockers(self) -> None:
        self.tournament_with(self.keeper, title="One")
        self.tournament_with(self.dup, title="Two")

        self.assertEqual(blockers([self.keeper, self.dup]), [])


class TestReview(TeamMergeTestCase):
    def test_the_most_used_team_is_kept_by_default(self) -> None:
        self.tournament_with(self.dup, title="One")
        self.assertEqual(default_keeper([self.keeper, self.dup]), self.dup)
        self.assertEqual(default_keeper([self.keeper, self.rival]), self.keeper)

    def test_compare_marks_identity_rows_that_differ(self) -> None:
        lines = {line.label: line for line in compare([self.keeper, self.dup])}
        self.assertEqual(lines["City"].values, ["", "Pune"])
        self.assertFalse(lines["City"].differs)
        self.assertFalse(lines["Name"].differs)
        # The kept name survives as written, so a change of case counts.
        lowered = Team.objects.create(name="goosebumps")
        self.assertTrue({x.label: x for x in compare([self.keeper, lowered])}["Name"].differs)
        self.rival.city = "Delhi"
        self.dup.city = "Pune"
        self.assertTrue({x.label: x for x in compare([self.rival, self.dup])}["City"].differs)


@override_settings(STORAGES=STATIC)
class TestMergeAdmin(TeamMergeTestCase):
    def staff(self, *codenames: str) -> User:
        staff = User.objects.create(username="s@x.com", email="s@x.com", is_staff=True)
        staff.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        self.client.force_login(staff)
        return staff

    def post(self, **extra: object) -> object:
        return self.client.post(
            "/admin/server/team/",
            {
                "action": "merge_teams",
                "_selected_action": [self.keeper.pk, self.dup.pk],
                **extra,
            },
        )

    def test_the_action_shows_a_review_first(self) -> None:
        self.staff("view_team", "change_team", "delete_team")
        response = self.post()
        # A staff merge has no request to reject.
        self.assertNotContains(response, "Reject request")  # type: ignore[arg-type]
        self.assertEqual(response.status_code, 200)  # type: ignore[attr-defined]
        self.assertContains(response, 'type="radio" name="keeper"', count=2)  # type: ignore[arg-type]
        self.assertContains(response, f'merge-gone">Goosebumps #{self.dup.pk}</span> will be deleted')  # type: ignore[arg-type]
        self.assertTrue(Team.objects.filter(pk=self.dup.pk).exists())

    def test_confirming_merges_into_the_chosen_team(self) -> None:
        staff = self.staff("view_team", "change_team", "delete_team")
        response = self.post(merge_confirmed="yes", keeper=self.dup.pk)
        self.assertEqual(response.status_code, 302)  # type: ignore[attr-defined]
        followed = self.client.get(response["Location"])  # type: ignore[index]
        self.assertContains(followed, f"Merged Goosebumps #{self.keeper.pk} into")
        self.assertEqual(list(Team.objects.filter(name__startswith="Goose")), [self.dup])
        self.assertEqual(TeamMerge.objects.get().merged_by, staff)

    def test_a_blocked_merge_cannot_be_confirmed(self) -> None:
        self.tournament_with(self.keeper, self.dup)
        self.staff("view_team", "change_team", "delete_team")
        response = self.post()
        self.assertContains(response, "were both at Nationals")  # type: ignore[arg-type]
        self.assertContains(response, "can&#x27;t be merged")  # type: ignore[arg-type]
        self.assertNotContains(response, 'class="merge-confirm"')  # type: ignore[arg-type]
        self.post(merge_confirmed="yes", keeper=self.keeper.pk)
        self.assertTrue(Team.objects.filter(pk=self.dup.pk).exists())

    def test_changing_teams_is_not_enough(self) -> None:
        self.staff("view_team", "change_team")
        self.post(merge_confirmed="yes", keeper=self.keeper.pk)
        self.assertTrue(Team.objects.filter(pk=self.dup.pk).exists())

    def test_a_keeper_outside_the_selection_is_refused(self) -> None:
        self.staff("view_team", "change_team", "delete_team")
        self.post(merge_confirmed="yes", keeper=self.rival.pk)
        self.assertEqual(Team.objects.count(), 3)


class TestTeamAdminsMerge(TeamMergeTestCase):
    """A team admin merges teams they admin, and asks staff about the rest."""

    def setUp(self) -> None:
        super().setUp()
        self.keeper.admins.add(self.user)
        self.client.force_login(self.user)

    def preview(self, *teams: Team) -> Any:
        return self.client.post(
            "/api/team-merge/preview",
            {"team_ids": [team.pk for team in teams]},
            content_type="application/json",
        )

    def merge(self, keeper: Team, *teams: Team, message: str = "", logo: Team | None = None) -> Any:
        return self.client.post(
            "/api/team-merge/",
            {
                "team_ids": [team.pk for team in teams],
                "keeper_id": keeper.pk,
                "logo_id": logo and logo.pk,
                "message": message,
            },
            content_type="application/json",
        )

    def test_an_admin_of_every_team_merges_straight_away(self) -> None:
        self.dup.admins.add(self.user)
        preview = self.preview(self.keeper, self.dup).json()
        self.assertTrue(preview["can_merge"])
        self.assertEqual([team["id"] for team in preview["teams"]], [self.keeper.pk, self.dup.pk])

        response = self.merge(self.keeper, self.keeper, self.dup)

        self.assertEqual(
            response.json(), {"merged": True, "slug": self.keeper.slug, "request_id": None}
        )
        self.assertFalse(Team.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(TeamMerge.objects.get().merged_by, self.user)

    def test_an_admin_picks_the_logo(self) -> None:
        self.dup.admins.add(self.user)
        Team.objects.filter(pk=self.keeper.pk).update(image_url="https://x.com/kept.png")
        Team.objects.filter(pk=self.dup.pk).update(image_url="https://x.com/copy.png")

        self.merge(self.keeper, self.keeper, self.dup, logo=self.dup)

        self.keeper.refresh_from_db()
        self.assertEqual(self.keeper.image_url, "https://x.com/copy.png")

    def test_otherwise_staff_are_asked(self) -> None:
        preview = self.preview(self.keeper, self.dup).json()
        self.assertFalse(preview["can_merge"])
        self.assertEqual(preview["admin_of"], [self.keeper.pk])

        response = self.merge(
            self.keeper, self.keeper, self.dup, message="Same club, made twice", logo=self.dup
        )

        self.assertFalse(response.json()["merged"])
        self.assertTrue(Team.objects.filter(pk=self.dup.pk).exists())
        asked = ServiceRequest.objects.get(pk=response.json()["request_id"])
        self.assertEqual(asked.type, ServiceRequestType.REQUEST_TEAM_MERGE)
        self.assertEqual((asked.keep_team, asked.logo_team), (self.keeper, self.dup))
        self.assertEqual(set(asked.service_teams.all()), {self.keeper, self.dup})
        self.assertTrue(self.preview(self.keeper, self.dup).json()["pending"])

        again = self.merge(self.dup, self.keeper, self.dup, message="Again")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_a_merge_has_a_size_limit(self) -> None:
        many = [Team.objects.create(name=f"Copy {n}") for n in range(10)]
        self.assertEqual(self.preview(self.keeper, *many).status_code, 400)

    def test_a_request_says_why(self) -> None:
        response = self.merge(self.keeper, self.keeper, self.dup, message="  ")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_someone_who_admins_none_of_them_is_refused(self) -> None:
        self.keeper.admins.remove(self.user)
        self.assertEqual(self.preview(self.keeper, self.dup).status_code, 403)
        self.assertEqual(
            self.merge(self.keeper, self.keeper, self.dup, message="x").status_code, 403
        )
        self.assertEqual(Team.objects.count(), 3)

    def test_blocked_teams_can_be_neither_merged_nor_asked_about(self) -> None:
        self.tournament_with(self.keeper, self.dup, title="Nationals 2025")
        self.assertEqual(len(self.preview(self.keeper, self.dup).json()["blockers"]), 1)
        self.assertEqual(
            self.merge(self.keeper, self.keeper, self.dup, message="x").status_code, 400
        )
        self.dup.admins.add(self.user)
        self.assertEqual(self.merge(self.keeper, self.keeper, self.dup).status_code, 400)
        self.assertEqual(Team.objects.count(), 3)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_the_keeper_must_be_one_of_the_teams(self) -> None:
        self.dup.admins.add(self.user)
        self.rival.admins.add(self.user)
        self.assertEqual(self.merge(self.rival, self.keeper, self.dup).status_code, 400)
        self.assertEqual(Team.objects.count(), 3)

    def test_the_general_request_form_cannot_ask_for_a_team_merge(self) -> None:
        response = self.client.post(
            "/api/service-requests/",
            {"type": ServiceRequestType.REQUEST_TEAM_MERGE, "message": "x"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


@override_settings(STORAGES=STATIC)
class TestStaffDecideRequests(TeamMergeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.asked = ServiceRequest.objects.create(
            user=self.user,
            type=ServiceRequestType.REQUEST_TEAM_MERGE,
            message="Same club, made twice",
            keep_team=self.dup,
        )
        self.asked.service_teams.set([self.keeper, self.dup])
        self.staff = User.objects.create(username="s@x.com", email="s@x.com", is_staff=True)
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_servicerequest", "change_servicerequest", "delete_team"]
            )
        )
        self.client.force_login(self.staff)

    def post(self, action: str, **extra: object) -> Any:
        return self.client.post(
            "/admin/server/servicerequest/",
            {"action": action, "_selected_action": [self.asked.pk], **extra},
        )

    def test_staff_review_then_merge_into_the_team_asked_for(self) -> None:
        self.dup.admins.add(self.staff)
        review = self.post("approve_team_merge")
        self.assertContains(review, "Same club, made twice")
        # The asker admins neither team here, and staff can see who does.
        self.assertContains(review, "They admin none of these teams")
        self.assertContains(review, "s@x.com")
        self.assertContains(review, f'value="{self.dup.pk}" checked')

        self.post("approve_team_merge", merge_confirmed="yes", keeper=self.dup.pk)

        self.assertFalse(Team.objects.filter(pk=self.keeper.pk).exists())
        self.asked.refresh_from_db()
        self.assertEqual(self.asked.status, ServiceRequestStatus.APPROVED)
        self.assertEqual(TeamMerge.objects.get().merged_by, self.staff)
        self.assertEqual(mail.outbox[-1].to, [self.user.email])

    def test_staff_may_keep_another_team_than_the_one_asked_for(self) -> None:
        self.post("approve_team_merge", merge_confirmed="yes", keeper=self.keeper.pk)

        self.assertFalse(Team.objects.filter(pk=self.dup.pk).exists())
        self.asked.refresh_from_db()
        self.assertEqual(self.asked.status, ServiceRequestStatus.APPROVED)
        self.assertEqual(self.asked.keep_team, self.keeper)
        self.assertEqual(mail.outbox[-1].to, [self.user.email])

    def test_staff_see_the_logo_asked_for_and_may_change_it(self) -> None:
        Team.objects.filter(pk=self.keeper.pk).update(image_url="https://x.com/a.png")
        Team.objects.filter(pk=self.dup.pk).update(image_url="https://x.com/b.png")
        self.asked.logo_team = self.keeper
        self.asked.save()

        review = self.post("approve_team_merge")
        self.assertContains(review, f'type="radio" name="logo" value="{self.keeper.pk}" checked')

        self.post("approve_team_merge", merge_confirmed="yes", keeper=self.dup.pk, logo=self.dup.pk)
        self.dup.refresh_from_db()
        self.assertEqual(self.dup.image_url, "https://x.com/b.png")

    def test_one_logo_is_no_choice(self) -> None:
        Team.objects.filter(pk=self.dup.pk).update(image_url="https://x.com/b.png")
        self.assertNotContains(self.post("approve_team_merge"), 'type="radio" name="logo"')

    def test_the_review_page_can_reject_too(self) -> None:
        review = self.post("approve_team_merge")
        self.assertContains(review, 'value="reject_team_merge"')
        self.assertContains(review, "Reject request")

    def test_staff_reject(self) -> None:
        self.post("reject_team_merge")
        self.asked.refresh_from_db()
        self.assertEqual(self.asked.status, ServiceRequestStatus.REJECTED)
        self.assertEqual(Team.objects.count(), 3)
        self.assertEqual(mail.outbox[-1].to, [self.user.email])

    def test_nobody_approves_their_own_request(self) -> None:
        self.asked.user = self.staff
        self.asked.save()
        self.post("approve_team_merge", merge_confirmed="yes", keeper=self.dup.pk)
        self.assertEqual(Team.objects.count(), 3)

    def test_approving_needs_the_right_to_delete_teams(self) -> None:
        self.staff.user_permissions.remove(Permission.objects.get(codename="delete_team"))
        self.client.force_login(User.objects.get(pk=self.staff.pk))
        self.post("approve_team_merge", merge_confirmed="yes", keeper=self.dup.pk)
        self.assertEqual(Team.objects.count(), 3)
