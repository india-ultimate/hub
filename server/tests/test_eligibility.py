import datetime

from django.test import TestCase

from server.membership import eligibility
from server.membership.models import Membership, MembershipPlan, MembershipType
from server.season.models import Season
from server.series.models import Role, Series, is_playing_role
from server.tournament.models import Event

from .test_membership_model import make_player


def make_event(name: str, start: str, end: str, needs_membership: bool = False) -> Event:
    return Event.objects.create(
        title=name,
        start_date=start,
        end_date=end,
        team_registration_start_date=start,
        team_registration_end_date=end,
        player_registration_start_date=start,
        player_registration_end_date=end,
        is_membership_needed=needs_membership,
    )


def make_series(season: Season | None, start: str = "2026-10-01") -> Series:
    return Series.objects.create(
        name="Club series",
        start_date=start,
        end_date="2027-03-31",
        type=Series.Type.MIXED,
        category=Series.Category.CLUB,
        season=season,
        series_roster_max_players=30,
        event_min_players_male=0,
        event_min_players_female=0,
        event_max_players_male=20,
        event_max_players_female=20,
    )


class TestEligibility(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.last_season = Season.objects.get(name="Season 2025-2026")
        self.gated = make_event("Nationals", "2026-11-01", "2026-11-03", True)
        self.private = make_event("Club friendly", "2026-11-01", "2026-11-03", False)
        self.player = make_player("j@example.com")

    def hold(self, slug: str | None, season: Season | None = None, **kwargs: object) -> Membership:
        season = season or self.season
        plan = (
            None
            if slug is None
            else MembershipPlan.objects.get(
                season=season, type=MembershipType.objects.get(slug=slug)
            )
        )
        defaults = {
            "is_active": True,
            "waiver_valid": True,
            "start_date": season.start_date,
            "end_date": season.end_date,
        }
        defaults.update(kwargs)
        return Membership.objects.create(player=self.player, season=season, plan=plan, **defaults)

    def action(self, target: Event | Series, is_playing: bool = True) -> str:
        error = eligibility.check(self.player, target, is_playing=is_playing)
        assert error is not None  # noqa: S101 — narrows for mypy
        return error["action_name"]

    def test_a_private_event_checks_nothing(self) -> None:
        self.assertIsNone(eligibility.check(self.player, self.private, is_playing=True))

    def test_a_regular_member_may_play_a_gated_event(self) -> None:
        self.hold("regular")
        self.assertIsNone(eligibility.check(self.player, self.gated, is_playing=True))

    def test_a_membership_with_no_tier_may_play_a_gated_event(self) -> None:
        self.hold(None)
        self.assertIsNone(eligibility.check(self.player, self.gated, is_playing=True))

    def test_a_community_member_may_not_play_a_gated_event(self) -> None:
        self.hold("community")
        error = eligibility.check(self.player, self.gated, is_playing=True)
        assert error is not None  # noqa: S101 — narrows for mypy
        self.assertEqual(error["action_name"], "Upgrade membership")
        self.assertEqual(
            error["description"],
            "Community Membership does not cover playing here. Playing needs "
            "Patron member, Regular Annual Membership or Discounted Membership.",
        )

    def test_a_community_member_may_be_staff_at_a_gated_event(self) -> None:
        self.hold("community")
        self.assertIsNone(eligibility.check(self.player, self.gated, is_playing=False))

    def test_no_membership_is_refused(self) -> None:
        self.assertEqual(self.action(self.gated), "Get membership")

    def test_an_inactive_membership_is_refused(self) -> None:
        self.hold("regular", is_active=False)
        self.assertEqual(self.action(self.gated), "Get membership")

    def test_an_unsigned_waiver_is_refused(self) -> None:
        self.hold("regular", waiver_valid=False)
        self.assertEqual(self.action(self.gated), "Sign waiver")

    def test_last_season_does_not_cover_this_season_s_event(self) -> None:
        self.hold(None, season=self.last_season)
        self.assertEqual(self.action(self.gated), "Get membership")

    def test_this_season_does_not_cover_last_season_s_event(self) -> None:
        self.hold("regular")
        old_event = make_event("Old nationals", "2025-12-01", "2025-12-03", True)
        self.assertEqual(self.action(old_event), "Get membership")

    def test_a_refunded_membership_does_not_count(self) -> None:
        self.hold(
            "regular",
            refunded_at=datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(self.action(self.gated), "Get membership")

    def test_an_event_in_no_season_is_refused_clearly(self) -> None:
        # Review Focus #3: an event before records began must not crash.
        ancient = make_event("Old tournament", "2019-01-01", "2019-01-02", True)
        self.assertEqual(
            eligibility.check(self.player, ancient, is_playing=True),
            {
                "message": "No season for this event",
                "description": (
                    "This event's dates fall outside every season, so membership "
                    "cannot be checked. Ask an admin to add the season."
                ),
            },
        )

    def test_a_series_event_is_gated_by_the_series_season_even_with_the_flag_off(self) -> None:
        series = make_series(self.season)
        self.private.series = series
        self.private.save()
        self.hold("community")
        self.assertEqual(self.action(self.private), "Upgrade membership")
        self.assertIsNone(eligibility.check(self.player, series, is_playing=False))
        self.assertEqual(self.action(series), "Upgrade membership")

    def test_a_series_season_wins_over_the_event_date(self) -> None:
        # The event falls in 2026-27, but the series belongs to 2025-26.
        self.gated.series = make_series(self.last_season)
        self.gated.save()
        self.hold("regular", season=self.last_season)
        self.assertIsNone(eligibility.check(self.player, self.gated, is_playing=True))

    def test_a_series_with_no_season_falls_back_to_its_start_date(self) -> None:
        series = make_series(None, start="2026-10-01")
        self.hold("regular")
        self.assertIsNone(eligibility.check(self.player, series, is_playing=True))

    def test_a_series_event_with_no_series_season_falls_back_to_the_event_date(self) -> None:
        # The series starts in 2025-26, the event in 2026-27: the event's date counts.
        self.private.series = make_series(None, start="2026-01-01")
        self.private.save()
        self.hold("regular")
        self.assertIsNone(eligibility.check(self.player, self.private, is_playing=True))

    def test_only_player_captain_and_spirit_captain_are_playing_roles(self) -> None:
        self.assertTrue(is_playing_role("DFLT"))
        self.assertFalse(is_playing_role("COACH"))
        playing = {r for r in Role if is_playing_role(r)}
        self.assertEqual(playing, {Role.DEFAULT, Role.CAPTAIN, Role.SPIRIT_CAPTAIN})
