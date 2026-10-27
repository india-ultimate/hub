import datetime
from unittest import mock

from django.contrib.auth.models import Permission
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
from server.registration.models import RosterEntry
from server.series.models import Series, SeriesRegistration
from server.tests.base import create_event, create_player
from server.tournament.models import (
    Bracket,
    Match,
    MatchEvent,
    MatchStats,
    Pool,
    Registration,
    SwissRound,
    Tournament,
)
from server.transaction.models import RazorpayTransaction

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

    def test_details_the_kept_team_lacks_are_filled_from_the_copy(self) -> None:
        self.keeper.city = "Mumbai"
        self.keeper.save()

        merge_teams(self.keeper, [self.dup])

        self.keeper.refresh_from_db()
        self.assertEqual(self.keeper.name, "Goosebumps")
        self.assertEqual(self.keeper.city, "Mumbai")
        self.assertEqual(self.keeper.ultimate_central_id, 212436)

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
