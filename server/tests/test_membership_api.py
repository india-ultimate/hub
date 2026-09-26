from server.core.models import Guardianship, User
from server.membership.models import Membership
from server.season.models import Season
from server.tests.base import ApiBaseTestCase


class TestPlansEndpoint(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()
        self.s26 = Season.objects.get(name="Season 2026-2027")

    def test_the_four_tiers_are_offered_with_prices(self) -> None:
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans")
        self.assertEqual(response.status_code, 200)
        by_slug = {plan["slug"]: plan for plan in response.json()}
        self.assertEqual(by_slug["regular"]["amount"], 75000)
        self.assertEqual(by_slug["community"]["amount"], 25000)

    def test_a_tier_needing_approval_is_marked_unavailable_without_one(self) -> None:
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        by_slug = {plan["slug"]: plan for plan in response.json()}
        self.assertFalse(by_slug["discounted"]["available_to_player"])
        self.assertTrue(by_slug["regular"]["available_to_player"])

    def test_a_stranger_cannot_price_someone_else(self) -> None:
        self.client.force_login(User.objects.create(username="nosy", email="nosy@example.com"))
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        self.assertEqual(response.status_code, 403)

    def test_a_guardian_may_price_their_ward(self) -> None:
        guardian = User.objects.create(username="parent", email="parent@example.com")
        Guardianship.objects.create(
            user=guardian, player=self.player, relation=Guardianship.Relation.MO
        )
        self.client.force_login(guardian)
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        self.assertEqual(response.status_code, 200)

    def test_a_season_with_no_plans_returns_an_empty_list(self) -> None:
        empty = Season.objects.create(
            name="Season 2030-2031", start_date="2030-08-01", end_date="2031-07-31"
        )
        response = self.client.get(f"/api/seasons/{empty.id}/plans")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class TestMembershipHistory(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()

    def test_history_lists_every_season(self) -> None:
        for name in ("Season 2025-2026", "Season 2026-2027"):
            season = Season.objects.get(name=name)
            Membership.objects.create(
                player=self.player,
                season=season,
                is_active=True,
                start_date=season.start_date,
                end_date=season.end_date,
            )
        response = self.client.get(f"/api/players/{self.player.id}/memberships")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 2)
        # Newest first, and a row with no plan predates the catalog, so it
        # allows everything.
        self.assertEqual(body[0]["season"], Season.objects.get(name="Season 2026-2027").id)
        self.assertIsNone(body[0]["tier"])
        self.assertIn("play_championships", body[0]["scopes"])

    def test_the_number_is_not_in_the_public_player_list(self) -> None:
        self.player.membership_number = "IU-26-0001"
        self.player.save(update_fields=["membership_number"])
        response = self.client.get("/api/players")
        for entry in response.json():
            self.assertNotIn("membership_number", entry)
