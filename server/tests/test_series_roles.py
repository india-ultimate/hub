"""A place on a series roster is decided by the role, not by a flag."""

from typing import Any

from django.test import TestCase

from server.core.models import Player, Team, User
from server.season.models import Season
from server.series.models import Role, Series, SeriesRegistration, SeriesRosterInvitation
from server.series.utils import change_series_role, register_player
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.tournament.models import Event, Registration, Tournament

from .test_eligibility import make_series
from .test_subscription_model import make_player


class TestSeriesRoles(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(self.season)
        self.series.series_roster_max_players = 1
        self.series.save()
        self.team = Team.objects.create(name="Team A")
        self.other_team = Team.objects.create(name="Team B")

    def member(self, email: str, slug: str) -> Player:
        player = make_player(email)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=SubscriptionPlan.objects.get(
                season=self.season, type=SubscriptionType.objects.get(slug=slug)
            ),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        return player

    def test_a_community_member_may_coach_but_not_play(self) -> None:
        player = self.member("coach@example.com", "community")

        registration, error = register_player(self.series, self.team, player, Role.COACH)
        self.assertIsNone(error)
        self.assertIsNotNone(registration)

        SeriesRegistration.objects.all().delete()
        registration, error = register_player(self.series, self.team, player, Role.DEFAULT)
        self.assertIsNone(registration)
        assert error is not None  # noqa: S101 - narrows the type
        self.assertIn("does not cover playing", error["message"])

    def test_staff_do_not_take_a_player_spot(self) -> None:
        playing = self.member("player@example.com", "regular")
        manager = self.member("manager@example.com", "regular")

        _, error = register_player(self.series, self.team, playing, Role.DEFAULT)
        self.assertIsNone(error)

        # The cap is one player per team, and it is taken.
        _, full = register_player(self.series, self.team, manager, Role.DEFAULT)
        assert full is not None  # noqa: S101 - narrows the type
        self.assertIn("Only 1 players", full["message"])

        _, error = register_player(self.series, self.team, manager, Role.MANAGER)
        self.assertIsNone(error)

    def test_staff_may_take_a_second_team_but_players_may_not(self) -> None:
        player = self.member("both@example.com", "regular")
        self.series.series_roster_max_players = 10
        self.series.save()

        _, error = register_player(self.series, self.team, player, Role.DEFAULT)
        self.assertIsNone(error)

        # Playing for a second team is refused, coaching it is not.
        _, error = register_player(self.series, self.other_team, player, Role.DEFAULT)
        assert error is not None  # noqa: S101 - narrows the type
        self.assertIn("1 club/state/national team", error["message"])

        _, error = register_player(self.series, self.other_team, player, Role.COACH)
        self.assertIsNone(error)

    def test_a_role_change_is_checked_the_same_way(self) -> None:
        player = self.member("switch@example.com", "community")
        registration, error = register_player(self.series, self.team, player, Role.COACH)
        assert registration is not None  # noqa: S101 - narrows the type

        error = change_series_role(registration, Role.DEFAULT)
        assert error is not None  # noqa: S101 - narrows the type
        self.assertIn("does not cover playing", error["message"])
        registration.refresh_from_db()
        self.assertEqual(Role.COACH, registration.role)

        self.assertIsNone(change_series_role(registration, Role.MANAGER))
        registration.refresh_from_db()
        self.assertEqual(Role.MANAGER, registration.role)

    def test_a_player_can_be_promoted_to_captain_on_their_own_team(self) -> None:
        """The row being edited must not collide with itself: both roles are
        playing roles, so the one-team rule would otherwise refuse it."""
        player = self.member("captain@example.com", "regular")
        registration, error = register_player(self.series, self.team, player, Role.DEFAULT)
        assert registration is not None  # noqa: S101 - narrows the type

        self.assertIsNone(change_series_role(registration, Role.CAPTAIN))
        registration.refresh_from_db()
        self.assertEqual(Role.CAPTAIN, registration.role)

    def test_a_school_series_still_refuses_a_second_playing_team(self) -> None:
        self.series.category = Series.Category.SCHOOL
        self.series.series_roster_max_players = 10
        self.series.save()
        for team in (self.team, self.other_team):
            team.category = Team.CategoryTypes.SCHOOL
            team.save()
        player = self.member("school@example.com", "regular")

        registration, error = register_player(self.series, self.team, player, Role.DEFAULT)
        assert registration is not None  # noqa: S101 - narrows the type

        second, error = register_player(self.series, self.other_team, player, Role.COACH)
        assert second is not None  # noqa: S101 - narrows the type
        error = change_series_role(second, Role.DEFAULT)
        assert error is not None  # noqa: S101 - narrows the type
        self.assertIn("1 school team", error["message"])


class TestEventCapOnRoleChange(TestCase):
    """Promoting someone already on an event roster must clear the same
    caps as adding them. Otherwise staff are a way past a full event."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(self.season)
        self.series.event_max_players_total = 1
        self.series.save()
        self.team = Team.objects.create(name="Team A")
        self.series.teams.add(self.team)

        self.admin = User.objects.create(username="admin@example.com", email="admin@example.com")
        self.team.admins.add(self.admin)

        self.event = Event.objects.create(
            title="Sectionals",
            start_date="2026-11-01",
            end_date="2026-11-03",
            team_registration_start_date="2026-10-01",
            team_registration_end_date="2026-10-10",
            player_registration_start_date="2026-10-01",
            player_registration_end_date="2026-10-10",
            series=self.series,
        )
        self.tournament = Tournament.objects.create(event=self.event)
        self.tournament.teams.add(self.team)

        self.playing = self.rostered("playing@example.com", Role.DEFAULT, is_playing=True)
        self.staff = self.rostered("staff@example.com", Role.MANAGER, is_playing=False)

        self.client.force_login(self.admin)

    def rostered(self, email: str, role: str, is_playing: bool) -> Registration:
        player = make_player(email)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=SubscriptionPlan.objects.get(
                season=self.season, type=SubscriptionType.objects.get(slug="regular")
            ),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        SeriesRegistration.objects.create(
            series=self.series, team=self.team, player=player, role=role
        )
        return Registration.objects.create(
            event=self.event, team=self.team, player=player, is_playing=is_playing
        )

    def roster_url(self, registration: Registration) -> str:
        return f"/api/tournament/{self.event.id}/team/{self.team.id}/roster/{registration.id}"

    def test_a_promotion_cannot_over_fill_a_full_event(self) -> None:
        # Staff first take a playing spot on the series roster...
        series_registration = SeriesRegistration.objects.get(player=self.staff.player)
        self.assertIsNone(change_series_role(series_registration, Role.DEFAULT))

        # ... then try to carry it onto an event whose one spot is taken.
        response = self.client.put(
            self.roster_url(self.staff),
            data={"role": Role.DEFAULT, "is_playing": True},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("1 total players", response.json()["message"])
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_playing)

    def test_a_promotion_within_the_cap_is_allowed(self) -> None:
        self.series.event_max_players_total = 2
        self.series.save()
        series_registration = SeriesRegistration.objects.get(player=self.staff.player)
        self.assertIsNone(change_series_role(series_registration, Role.DEFAULT))

        response = self.client.put(
            self.roster_url(self.staff),
            data={"role": Role.DEFAULT, "is_playing": True},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_playing)


class TestSeriesRoleEndpoint(TestCase):
    """PUT /series/{slug}/team/{slug}/roster/{id}/role, as a team admin would."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(self.season)
        self.series.series_roster_max_players = 1
        self.series.save()
        self.team = Team.objects.create(name="Team A")
        self.series.teams.add(self.team)
        self.admin = User.objects.create(username="admin@example.com", email="admin@example.com")
        self.team.admins.add(self.admin)
        self.client.force_login(self.admin)

    def rostered(self, email: str, slug: str, role: str) -> SeriesRegistration:
        player = make_player(email)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=SubscriptionPlan.objects.get(season=self.season, type__slug=slug),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        registration, error = register_player(self.series, self.team, player, role)
        assert registration is not None, error  # noqa: S101 - narrows the type
        return registration

    def put_role(
        self, registration: SeriesRegistration, role: str, series: str = "", team: str = ""
    ) -> Any:
        url = (
            f"/api/series/{series or self.series.slug}/team/{team or self.team.slug}"
            f"/roster/{registration.id}/role"
        )
        return self.client.put(url, data={"role": role}, content_type="application/json")

    def assert_role(self, registration: SeriesRegistration, role: str) -> None:
        registration.refresh_from_db()
        self.assertEqual(role, registration.role)

    def test_a_team_admin_can_change_a_role(self) -> None:
        registration = self.rostered("cap@example.com", "regular", Role.DEFAULT)
        response = self.put_role(registration, Role.CAPTAIN)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(Role.CAPTAIN, response.json()["role"])
        self.assert_role(registration, Role.CAPTAIN)

    def test_someone_who_is_not_a_team_admin_is_refused(self) -> None:
        registration = self.rostered("cap@example.com", "regular", Role.DEFAULT)
        self.client.force_login(User.objects.create(username="nosy", email="nosy@example.com"))
        response = self.put_role(registration, Role.CAPTAIN)
        self.assertEqual(401, response.status_code)
        self.assert_role(registration, Role.DEFAULT)

    def test_an_invalid_role_is_refused(self) -> None:
        registration = self.rostered("cap@example.com", "regular", Role.DEFAULT)
        response = self.put_role(registration, "BOSS")
        self.assertEqual(400, response.status_code)
        self.assertEqual("Invalid role", response.json()["message"])
        self.assert_role(registration, Role.DEFAULT)

    def test_an_unknown_series_team_or_registration_is_refused(self) -> None:
        registration = self.rostered("cap@example.com", "regular", Role.DEFAULT)
        for response in (
            self.put_role(registration, Role.CAPTAIN, series="nope"),
            self.put_role(registration, Role.CAPTAIN, team="nope"),
        ):
            self.assertEqual(400, response.status_code)
            self.assertEqual("Series/Team does not exist", response.json()["message"])

        # A registration on another team's roster is not this team's to change.
        other = Team.objects.create(name="Team B")
        other.admins.add(self.admin)
        response = self.put_role(registration, Role.CAPTAIN, team=str(other.slug))
        self.assertEqual(400, response.status_code)
        self.assertEqual("Registration does not exist", response.json()["message"])
        self.assert_role(registration, Role.DEFAULT)

    def test_a_promotion_the_subscription_does_not_cover_is_refused(self) -> None:
        registration = self.rostered("coach@example.com", "community", Role.COACH)
        response = self.put_role(registration, Role.DEFAULT)
        self.assertEqual(400, response.status_code)
        self.assertIn("does not cover playing", response.json()["message"])
        self.assert_role(registration, Role.COACH)

    def test_a_promotion_past_the_roster_cap_is_refused(self) -> None:
        self.rostered("player@example.com", "regular", Role.DEFAULT)
        manager = self.rostered("manager@example.com", "regular", Role.MANAGER)
        response = self.put_role(manager, Role.DEFAULT)
        self.assertEqual(400, response.status_code)
        self.assertIn("Only 1 players", response.json()["message"])
        self.assert_role(manager, Role.MANAGER)

    def test_an_invitation_with_an_invalid_role_is_refused(self) -> None:
        player = make_player("invitee@example.com")
        response = self.client.post(
            f"/api/series/{self.series.slug}/team/{self.team.slug}/invitation",
            data={"to_player_id": player.id, "expires_on": None, "role": "BOSS"},
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Invalid role", response.json()["message"])
        self.assertFalse(SeriesRosterInvitation.objects.exists())
