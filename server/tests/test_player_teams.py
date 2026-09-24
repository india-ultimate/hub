from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Player, Team, User
from server.series.models import Series, SeriesRegistration
from server.tests.base import create_event, create_player
from server.tournament.models import Registration


class TestPlayerTeamsFollowRosters(TestCase):
    """`Player.teams` is what the profile, the player search and the chat tools
    read to say who someone plays for. It used to hold Ultimate Central history
    and nothing else; these cover it now following the rosters."""

    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create(username="player@example.com", email="player@example.com")
        self.player = create_player(self.user)
        self.team = Team.objects.create(name="Tigers")
        self.other_team = Team.objects.create(name="Lions")
        self.event = create_event("Nationals")
        self.series = Series.objects.create(
            name="NCS",
            start_date=now().date(),
            end_date=now().date(),
            type=Series.Type.MIXED,
            category=Series.Category.CLUB,
            series_roster_max_players=20,
            event_min_players_male=10,
            event_min_players_female=10,
            event_max_players_male=12,
            event_max_players_female=12,
        )

    def teams_of_player(self) -> list[Team]:
        return list(self.player.teams.all())

    def test_rostering_onto_an_event_puts_the_team_on_the_profile(self) -> None:
        Registration.objects.create(event=self.event, player=self.player, team=self.team)

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_a_series_roster_counts_too(self) -> None:
        SeriesRegistration.objects.create(series=self.series, player=self.player, team=self.team)

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_a_coach_who_never_plays_is_still_on_the_team(self) -> None:
        Registration.objects.create(
            event=self.event,
            player=self.player,
            team=self.team,
            role=Registration.Role.COACH,
            is_playing=False,
        )

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_taking_them_off_the_roster_takes_the_team_back_off(self) -> None:
        registration = Registration.objects.create(
            event=self.event, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [])

    def test_leaving_the_series_roster_takes_the_team_off(self) -> None:
        registration = SeriesRegistration.objects.create(
            series=self.series, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [])

    def test_a_roster_removal_also_drops_a_matching_import_link(self) -> None:
        """Accepted, not an oversight: nothing records whether a link came from
        a roster or from the Ultimate Central import, and a provenance column
        is more than this field is worth. 677 pairs on production are both."""
        self.player.teams.add(self.team)
        registration = Registration.objects.create(
            event=self.event, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [])

    def test_the_team_stays_while_another_roster_still_holds_them(self) -> None:
        """A season roster and an event roster reach the same team. Leaving one
        says nothing about the other."""
        SeriesRegistration.objects.create(series=self.series, player=self.player, team=self.team)
        registration = Registration.objects.create(
            event=self.event, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_the_team_stays_while_a_second_event_still_holds_them(self) -> None:
        second_event = create_event("Sectionals")
        Registration.objects.create(event=self.event, player=self.player, team=self.team)
        registration = Registration.objects.create(
            event=second_event, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_leaving_one_team_does_not_touch_another(self) -> None:
        second_event = create_event("Sectionals")
        Registration.objects.create(event=self.event, player=self.player, team=self.team)
        registration = Registration.objects.create(
            event=second_event, player=self.player, team=self.other_team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [self.team])

    def test_deleting_the_event_takes_the_team_off_as_well(self) -> None:
        """The roster row goes with the event, and nothing is left to say the
        player was ever on that team."""
        Registration.objects.create(event=self.event, player=self.player, team=self.team)

        self.event.delete()

        self.assertEqual(self.teams_of_player(), [])

    def test_an_ultimate_central_team_with_no_roster_is_left_alone(self) -> None:
        """The import added teams the Hub has no roster for. Leaving an unrelated
        roster must not tidy those away."""
        self.player.teams.add(self.other_team)
        registration = Registration.objects.create(
            event=self.event, player=self.player, team=self.team
        )

        registration.delete()

        self.assertEqual(self.teams_of_player(), [self.other_team])

    def test_saving_a_registration_again_changes_nothing(self) -> None:
        """`calculate_player_points` re-saves every registration each night."""
        registration = Registration.objects.create(
            event=self.event, player=self.player, team=self.team
        )
        self.player.teams.remove(self.team)

        registration.points = 10
        registration.save()

        self.assertEqual(self.teams_of_player(), [])

    def test_deleting_an_account_leaves_its_team_mates_alone(self) -> None:
        """Django takes the deleted player's own links down with them. What has
        to hold is that the unlinking, running in the middle of that cascade,
        keeps to the player being deleted and leaves the rest of the team."""
        team_mate = create_player(
            User.objects.create(username="mate@example.com", email="mate@example.com")
        )
        Registration.objects.create(event=self.event, player=self.player, team=self.team)
        SeriesRegistration.objects.create(series=self.series, player=team_mate, team=self.team)

        self.user.delete()

        self.assertEqual(list(team_mate.teams.all()), [self.team])
        self.assertEqual(Player.teams.through.objects.count(), 1)

    def test_rostering_the_same_team_twice_leaves_one_link(self) -> None:
        second_event = create_event("Sectionals")
        Registration.objects.create(event=self.event, player=self.player, team=self.team)
        Registration.objects.create(event=second_event, player=self.player, team=self.team)

        self.assertEqual(Player.teams.through.objects.count(), 1)
