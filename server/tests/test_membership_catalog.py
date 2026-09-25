from django.db.utils import IntegrityError
from django.test import TestCase

from server.membership.models import MembershipPlan, MembershipType, MembershipTypeScope, Scope
from server.season.models import Season


class TestCatalog(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.create(
            name="Season 2026-2027", start_date="2026-08-01", end_date="2027-07-31"
        )
        self.regular = MembershipType.objects.create(
            slug="regular", name="Regular Annual Membership", display_order=2
        )
        self.community = MembershipType.objects.create(
            slug="community", name="Community Membership", display_order=4
        )
        for scope in (Scope.PLAY_CHAMPIONSHIPS, Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE):
            MembershipTypeScope.objects.create(type=self.regular, scope=scope)
        for scope in (Scope.STAFF_CHAMPIONSHIPS, Scope.VOTE):
            MembershipTypeScope.objects.create(type=self.community, scope=scope)

    def test_a_tier_allows_only_the_scopes_it_has(self) -> None:
        self.assertTrue(self.regular.allows(Scope.PLAY_CHAMPIONSHIPS))
        self.assertTrue(self.community.allows(Scope.STAFF_CHAMPIONSHIPS))
        self.assertFalse(self.community.allows(Scope.PLAY_CHAMPIONSHIPS))

    def test_a_tier_is_offered_once_per_season(self) -> None:
        MembershipPlan.objects.create(season=self.season, type=self.regular, amount=75000)
        with self.assertRaises(IntegrityError):
            MembershipPlan.objects.create(season=self.season, type=self.regular, amount=80000)

    def test_a_scope_is_listed_once_per_tier(self) -> None:
        with self.assertRaises(IntegrityError):
            MembershipTypeScope.objects.create(type=self.regular, scope=Scope.VOTE)
