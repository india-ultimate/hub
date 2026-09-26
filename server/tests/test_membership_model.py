import datetime

from django.db.utils import IntegrityError
from django.test import TestCase

from server.core.models import Player, User
from server.membership import numbers
from server.membership.models import Membership, MembershipPlan, MembershipType, Scope
from server.schema import MembershipSchema
from server.season.models import Season


def make_player(email: str) -> Player:
    user = User.objects.create(username=email, email=email)
    return Player.objects.create(user=user, date_of_birth="2000-01-01")


class TestPerSeasonMemberships(TestCase):
    def setUp(self) -> None:
        self.s25 = Season.objects.get(name="Season 2025-2026")
        self.s26 = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("a@example.com")
        self.regular = MembershipType.objects.get(slug="regular")
        self.community = MembershipType.objects.get(slug="community")

    def test_a_player_may_hold_one_membership_per_season(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s25,
            start_date=self.s25.start_date,
            end_date=self.s25.end_date,
        )
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertEqual(self.player.memberships.count(), 2)

    def test_two_memberships_for_one_season_are_refused(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        with self.assertRaises(IntegrityError):
            Membership.objects.create(
                player=self.player,
                season=self.s26,
                start_date=self.s26.start_date,
                end_date=self.s26.end_date,
            )

    def test_what_a_membership_allows_comes_from_its_tier(self) -> None:
        plan = MembershipPlan.objects.get(season=self.s26, type=self.community)
        membership = Membership.objects.create(
            player=self.player,
            season=self.s26,
            plan=plan,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertTrue(membership.allows(Scope.STAFF_CHAMPIONSHIPS))
        self.assertFalse(membership.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_membership_with_no_tier_counts_as_a_full_one(self) -> None:
        # Everything before Community existed was a full membership.
        membership = Membership.objects.create(
            player=self.player,
            season=self.s25,
            plan=None,
            start_date=self.s25.start_date,
            end_date=self.s25.end_date,
        )
        self.assertTrue(membership.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_refunded_membership_is_left_out_of_every_lookup(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            is_active=False,
            refunded_at=datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc),
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertEqual(Membership.objects.for_season(self.s26).count(), 0)
        self.assertIsNone(self.player.current_membership)


class TestMembershipNumbers(TestCase):
    def setUp(self) -> None:
        self.s26 = Season.objects.get(name="Season 2026-2027")

    def test_the_number_says_which_season_someone_joined(self) -> None:
        player = make_player("b@example.com")
        self.assertEqual(numbers.assign_number(player, self.s26), "IU-26-0001")

    def test_numbers_run_on_within_a_season(self) -> None:
        first = numbers.assign_number(make_player("c@example.com"), self.s26)
        second = numbers.assign_number(make_player("d@example.com"), self.s26)
        self.assertEqual((first, second), ("IU-26-0001", "IU-26-0002"))

    def test_a_player_keeps_the_number_they_already_have(self) -> None:
        player = make_player("e@example.com")
        first = numbers.assign_number(player, self.s26)
        s25 = Season.objects.get(name="Season 2025-2026")
        self.assertEqual(numbers.assign_number(player, s25), first)

    def test_numbers_continue_past_the_highest_in_that_season(self) -> None:
        taken = make_player("f@example.com")
        taken.membership_number = "IU-26-0041"
        taken.save(update_fields=["membership_number"])
        self.assertEqual(
            numbers.assign_number(make_player("g@example.com"), self.s26), "IU-26-0042"
        )


class TestMembershipSerialization(TestCase):
    def test_the_retired_fields_never_leave_the_model(self) -> None:
        # membership_number and is_annual are kept on Membership only so a
        # still-running previous release can read the columns during a
        # deploy; they must never reach the API.
        season = Season.objects.get(name="Season 2026-2027")
        player = make_player("h@example.com")
        membership = Membership.objects.create(
            player=player, season=season, start_date=season.start_date, end_date=season.end_date
        )
        serialized = MembershipSchema.from_orm(membership).dict()
        self.assertNotIn("membership_number", serialized)
        self.assertNotIn("is_annual", serialized)
