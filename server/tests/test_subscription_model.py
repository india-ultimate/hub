import datetime

from django.db.utils import IntegrityError
from django.test import TestCase

from server.core.models import Player, User
from server.schema import SubscriptionSchema
from server.season.models import Season
from server.subscription import numbers
from server.subscription.models import Scope, Subscription, SubscriptionPlan, SubscriptionType


def make_player(email: str) -> Player:
    user = User.objects.create(username=email, email=email)
    return Player.objects.create(user=user, date_of_birth="2000-01-01")


class TestPerSeasonSubscriptions(TestCase):
    def setUp(self) -> None:
        self.s25 = Season.objects.get(name="Season 2025-2026")
        self.s26 = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("a@example.com")
        self.regular = SubscriptionType.objects.get(slug="regular")
        self.community = SubscriptionType.objects.get(slug="community")

    def test_a_player_may_hold_one_subscription_per_season(self) -> None:
        Subscription.objects.create(
            player=self.player,
            season=self.s25,
            start_date=self.s25.start_date,
            end_date=self.s25.end_date,
        )
        Subscription.objects.create(
            player=self.player,
            season=self.s26,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertEqual(self.player.subscriptions.count(), 2)

    def test_two_subscriptions_for_one_season_are_refused(self) -> None:
        Subscription.objects.create(
            player=self.player,
            season=self.s26,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        with self.assertRaises(IntegrityError):
            Subscription.objects.create(
                player=self.player,
                season=self.s26,
                start_date=self.s26.start_date,
                end_date=self.s26.end_date,
            )

    def test_what_a_subscription_allows_comes_from_its_tier(self) -> None:
        plan = SubscriptionPlan.objects.get(season=self.s26, type=self.community)
        subscription = Subscription.objects.create(
            player=self.player,
            season=self.s26,
            plan=plan,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertTrue(subscription.allows(Scope.STAFF_CHAMPIONSHIPS))
        self.assertFalse(subscription.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_subscription_with_no_tier_counts_as_a_full_one(self) -> None:
        # Everything before Community existed was a full subscription.
        subscription = Subscription.objects.create(
            player=self.player,
            season=self.s25,
            plan=None,
            start_date=self.s25.start_date,
            end_date=self.s25.end_date,
        )
        self.assertTrue(subscription.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_refunded_subscription_is_left_out_of_every_lookup(self) -> None:
        Subscription.objects.create(
            player=self.player,
            season=self.s26,
            is_active=False,
            refunded_at=datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc),
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        self.assertEqual(Subscription.objects.for_season(self.s26).count(), 0)
        self.assertIsNone(self.player.current_subscription)


class TestSubscriptionNumbers(TestCase):
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
        taken.iu_id = "IU-26-0041"
        taken.save(update_fields=["iu_id"])
        self.assertEqual(
            numbers.assign_number(make_player("g@example.com"), self.s26), "IU-26-0042"
        )


class TestSubscriptionSerialization(TestCase):
    def test_the_retired_fields_never_leave_the_model(self) -> None:
        # subscription_number and is_annual are kept on Subscription only so a
        # still-running previous release can read the columns during a
        # deploy; they must never reach the API.
        season = Season.objects.get(name="Season 2026-2027")
        player = make_player("h@example.com")
        subscription = Subscription.objects.create(
            player=player, season=season, start_date=season.start_date, end_date=season.end_date
        )
        serialized = SubscriptionSchema.from_orm(subscription).dict()
        self.assertNotIn("subscription_number", serialized)
        self.assertNotIn("is_annual", serialized)
