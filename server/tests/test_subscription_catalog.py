import importlib

from django.apps import apps
from django.db.utils import IntegrityError
from django.test import TestCase

from server.season.models import Season
from server.subscription import catalog
from server.subscription.models import (
    Scope,
    SubscriptionPlan,
    SubscriptionType,
    SubscriptionTypeScope,
)


class TestCatalog(TestCase):
    def setUp(self) -> None:
        # Slugs distinct from the four the seed migration (0147) already puts
        # in every test database -- these tests are about the mechanics of
        # the catalog, not about the seeded tiers themselves.
        self.season = Season.objects.create(
            name="Season 2026-2027", start_date="2026-08-01", end_date="2027-07-31"
        )
        self.regular = SubscriptionType.objects.create(
            slug="test-regular", name="Regular Subscription", display_order=2
        )
        self.community = SubscriptionType.objects.create(
            slug="test-community", name="Community Subscription", display_order=4
        )
        for scope in (Scope.PLAY_CHAMPIONSHIPS, Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE):
            SubscriptionTypeScope.objects.create(type=self.regular, scope=scope)
        for scope in (Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE):
            SubscriptionTypeScope.objects.create(type=self.community, scope=scope)

    def test_a_tier_allows_only_the_scopes_it_has(self) -> None:
        self.assertTrue(self.regular.allows(Scope.PLAY_CHAMPIONSHIPS))
        self.assertTrue(self.community.allows(Scope.STAFF_CHAMPIONSHIPS))
        self.assertFalse(self.community.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_tier_is_offered_once_per_season(self) -> None:
        SubscriptionPlan.objects.create(season=self.season, type=self.regular, amount=75000)
        with self.assertRaises(IntegrityError):
            SubscriptionPlan.objects.create(season=self.season, type=self.regular, amount=80000)

    def test_a_scope_is_listed_once_per_tier(self) -> None:
        with self.assertRaises(IntegrityError):
            SubscriptionTypeScope.objects.create(type=self.regular, scope=Scope.VOTE)


class TestSeededCatalog(TestCase):
    def test_the_four_tiers_exist_with_the_right_scopes(self) -> None:
        expected = {
            "patron": {Scope.PLAY_CHAMPIONSHIPS, Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE},
            "regular": {Scope.PLAY_CHAMPIONSHIPS, Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE},
            "discounted": {Scope.PLAY_CHAMPIONSHIPS, Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE},
            "community": {Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE},
        }
        for slug, scopes in expected.items():
            tier = SubscriptionType.objects.get(slug=slug)
            actual = SubscriptionTypeScope.objects.filter(type=tier).values_list("scope", flat=True)
            self.assertEqual(set(actual), scopes, slug)

    def test_only_the_discounted_tier_needs_a_grant(self) -> None:
        needs = set(
            SubscriptionType.objects.filter(requires_grant=True).values_list("slug", flat=True)
        )
        self.assertEqual(needs, {"discounted"})

    def test_community_cannot_play_championships(self) -> None:
        community = SubscriptionType.objects.get(slug="community")
        self.assertFalse(community.allows(Scope.PLAY_CHAMPIONSHIPS))


class TestCopyPlans(TestCase):
    def test_a_new_season_takes_the_previous_prices(self) -> None:
        source = Season.objects.create(
            name="Season 2026-2027", start_date="2026-08-01", end_date="2027-07-31"
        )
        target = Season.objects.create(
            name="Season 2027-2028", start_date="2027-08-01", end_date="2028-07-31"
        )
        regular = SubscriptionType.objects.get(slug="regular")
        SubscriptionPlan.objects.create(season=source, type=regular, amount=75000)

        copied = catalog.copy_plans(source, target)

        self.assertEqual(copied, 1)
        self.assertEqual(SubscriptionPlan.objects.get(season=target, type=regular).amount, 75000)

    def test_copying_twice_adds_nothing(self) -> None:
        source = Season.objects.create(
            name="Season 2026-2027", start_date="2026-08-01", end_date="2027-07-31"
        )
        target = Season.objects.create(
            name="Season 2027-2028", start_date="2027-08-01", end_date="2028-07-31"
        )
        regular = SubscriptionType.objects.get(slug="regular")
        SubscriptionPlan.objects.create(season=source, type=regular, amount=75000)

        catalog.copy_plans(source, target)
        self.assertEqual(catalog.copy_plans(source, target), 0)


class TestUnseed(TestCase):
    def test_rolling_back_only_removes_what_seed_created(self) -> None:
        """A plan the seed migration never created must survive its rollback."""
        unseed = importlib.import_module("server.migrations.0148_seed_catalog").unseed

        # Season 2022-2023 predates the catalog, so seed() put no plans on
        # it -- and a fresh tier (not one of the four seeded ones) keeps this
        # plan out of the seeded SubscriptionType rows entirely.
        legacy_season = Season.objects.get(name="Season 2022-2023")
        other_tier = SubscriptionType.objects.create(slug="not-seeded", name="Not seeded")
        extra_plan = SubscriptionPlan.objects.create(
            season=legacy_season, type=other_tier, amount=1
        )
        seeded_plan = SubscriptionPlan.objects.get(
            season__name="Season 2026-2027", type__slug="patron"
        )

        unseed(apps, None)

        self.assertTrue(SubscriptionPlan.objects.filter(pk=extra_plan.pk).exists())
        self.assertFalse(SubscriptionPlan.objects.filter(pk=seeded_plan.pk).exists())
