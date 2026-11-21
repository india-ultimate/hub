import datetime
from typing import Any

from server.core.models import Guardianship, Player, User
from server.season.models import Season
from server.subscription import sponsorship
from server.subscription.models import Subscription, SubscriptionPlan
from server.tests.base import ApiBaseTestCase
from server.utils import today


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
        self.assertFalse(by_slug["discounted"]["granted"])
        self.assertTrue(by_slug["regular"]["available_to_player"])

    def test_a_granted_tier_says_so(self) -> None:
        sponsorship.grant(self.player, self.s26)
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        by_slug = {plan["slug"]: plan for plan in response.json()}
        self.assertTrue(by_slug["discounted"]["granted"])
        self.assertTrue(by_slug["discounted"]["available_to_player"])
        # Only grant-only tiers are ever "granted".
        self.assertFalse(by_slug["regular"]["granted"])

    def test_each_tier_lists_its_features(self) -> None:
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans")
        by_slug = {plan["slug"]: plan for plan in response.json()}
        self.assertIn("Play in NCS tournaments", by_slug["regular"]["features"])
        # A "-" line is something the tier leaves out.
        self.assertTrue(any(f.startswith("-") for f in by_slug["community"]["features"]))

    def test_a_regular_holder_is_offered_patron_as_an_upgrade(self) -> None:
        Subscription.objects.create(
            player=self.player,
            season=self.s26,
            plan=SubscriptionPlan.objects.get(season=self.s26, type__slug="regular"),
            amount_paid=75000,
            is_active=True,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        by_slug = {plan["slug"]: plan for plan in response.json()}
        patron = by_slug["patron"]
        self.assertTrue(patron["available_to_player"])
        self.assertEqual(patron["upgrade_amount"], 75000)
        self.assertEqual(patron["upgrade_from"], "Regular Subscription")
        # What they hold and anything cheaper is not for sale, and not an upgrade.
        for slug in ("regular", "community"):
            self.assertFalse(by_slug[slug]["available_to_player"], slug)
            self.assertIsNone(by_slug[slug]["upgrade_from"], slug)
            self.assertIsNone(by_slug[slug]["upgrade_amount"], slug)

    def test_a_stranger_cannot_price_someone_else(self) -> None:
        self.client.force_login(User.objects.create(username="nosy", email="nosy@example.com"))
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        self.assertEqual(response.status_code, 403)

    def test_a_guardian_may_price_their_ward(self) -> None:
        guardian = User.objects.create(username="parent", email="parent@example.com")
        Player.objects.filter(pk=self.player.pk).update(
            date_of_birth=today() - datetime.timedelta(days=15 * 365)
        )
        Guardianship.objects.create(
            user=guardian, player=self.player, relation=Guardianship.Relation.MO
        )
        self.client.force_login(guardian)
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id={self.player.id}")
        self.assertEqual(response.status_code, 200)

    def test_an_unknown_player_is_a_404_not_the_unpriced_list(self) -> None:
        # Falling through to the unpriced list showed every tier as buyable.
        response = self.client.get(f"/api/seasons/{self.s26.id}/plans?player_id=99999")
        self.assertEqual(response.status_code, 404)

    def test_a_season_with_no_plans_returns_an_empty_list(self) -> None:
        empty = Season.objects.create(
            name="Season 2030-2031", start_date="2030-08-01", end_date="2031-07-31"
        )
        response = self.client.get(f"/api/seasons/{empty.id}/plans")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


class TestQuotesEndpoint(ApiBaseTestCase):
    """What the group-payment page shows each person: what they hold, and
    what they could be bought, at what they would pay."""

    def setUp(self) -> None:
        super().setUp()
        self.login()
        self.s26 = Season.objects.get(name="Season 2026-2027")

    def hold(self, player: Player, slug: str) -> None:
        plan = SubscriptionPlan.objects.get(season=self.s26, type__slug=slug)
        Subscription.objects.create(
            player=player,
            season=self.s26,
            plan=plan,
            amount_paid=plan.amount,
            is_active=True,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )

    def quotes(self, *ids: int) -> list[dict[str, Any]]:
        query = ",".join(str(i) for i in ids)
        response = self.client.get(f"/api/seasons/{self.s26.id}/quotes?player_ids={query}")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_a_community_holder_with_a_grant_is_offered_discounted_for_the_difference(
        self,
    ) -> None:
        self.hold(self.player, "community")
        sponsorship.grant(self.player, self.s26)
        [quote] = self.quotes(self.player.id)
        self.assertEqual(quote["player_id"], self.player.id)
        self.assertEqual(quote["held"], "Community Subscription")
        self.assertIn({"slug": "discounted", "kind": "upgrade", "amount": 5000}, quote["offers"])
        self.assertIn({"slug": "regular", "kind": "upgrade", "amount": 50000}, quote["offers"])
        self.assertNotIn("community", [offer["slug"] for offer in quote["offers"]])

    def test_a_newcomer_without_a_grant_gets_full_prices_and_no_discounted(self) -> None:
        [quote] = self.quotes(self.player.id)
        self.assertIsNone(quote["held"])
        self.assertEqual(
            [(o["slug"], o["kind"], o["amount"]) for o in quote["offers"]],
            [("patron", "new", 150000), ("regular", "new", 75000), ("community", "new", 25000)],
        )

    def test_a_patron_holder_has_no_offers(self) -> None:
        self.hold(self.player, "patron")
        [quote] = self.quotes(self.player.id)
        self.assertEqual((quote["held"], quote["offers"]), ("Patron Subscription", []))

    def test_unknown_ids_are_skipped_and_order_is_kept(self) -> None:
        other = User.objects.create(username="b@example.com", email="b@example.com")
        b = Player.objects.create(user=other, date_of_birth="2000-01-01")
        quotes = self.quotes(b.id, 999999, self.player.id)
        self.assertEqual([q["player_id"] for q in quotes], [b.id, self.player.id])

    def test_an_unknown_season_is_a_404(self) -> None:
        response = self.client.get(f"/api/seasons/999999/quotes?player_ids={self.player.id}")
        self.assertEqual(response.status_code, 404)

    def test_more_than_fifty_ids_is_refused(self) -> None:
        ids = ",".join(str(n) for n in range(1, 52))
        response = self.client.get(f"/api/seasons/{self.s26.id}/quotes?player_ids={ids}")
        self.assertEqual(response.status_code, 400)
        ids = ",".join(str(n) for n in range(1, 51))
        response = self.client.get(f"/api/seasons/{self.s26.id}/quotes?player_ids={ids}")
        self.assertEqual(response.status_code, 200)

    def test_no_ids_or_junk_is_an_empty_list(self) -> None:
        for query in ("", "?player_ids=", "?player_ids=abc,,"):
            response = self.client.get(f"/api/seasons/{self.s26.id}/quotes{query}")
            self.assertEqual(response.json(), [])


class TestSubscriptionHistory(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()

    def test_history_lists_every_season(self) -> None:
        for name in ("Season 2025-2026", "Season 2026-2027"):
            season = Season.objects.get(name=name)
            Subscription.objects.create(
                player=self.player,
                season=season,
                plan=(
                    SubscriptionPlan.objects.get(season=season, type__slug="regular")
                    if name == "Season 2025-2026"
                    else None
                ),
                is_active=True,
                start_date=season.start_date,
                end_date=season.end_date,
            )
        response = self.client.get(f"/api/players/{self.player.id}/subscriptions")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 2)
        # Newest first, and a row with no plan predates the catalog, so it
        # allows everything.
        self.assertEqual(body[0]["season"], Season.objects.get(name="Season 2026-2027").id)
        self.assertEqual(body[0]["season_name"], "Season 2026-2027")
        self.assertIsNone(body[0]["tier"])
        self.assertIsNone(body[0]["tier_name"])
        self.assertIn("play_championships", body[0]["scopes"])
        # People read the tier's name; code compares its slug.
        self.assertEqual(body[1]["tier"], "regular")
        self.assertEqual(body[1]["tier_name"], "Regular Subscription")

    def test_the_number_is_not_in_the_public_player_list(self) -> None:
        self.player.iu_id = "IU-26-0001"
        self.player.save(update_fields=["iu_id"])
        response = self.client.get("/api/players")
        self.assertNotIn("IU-26-0001", response.content.decode())


class TestSubscriptionHistoryIsPrivate(ApiBaseTestCase):
    """History carries amounts paid, refunds and the waiver signer's name."""

    def setUp(self) -> None:
        super().setUp()
        self.url = f"/api/players/{self.player.id}/subscriptions"

    def someone(self, username: str, **extra: bool) -> User:
        return User.objects.create(username=username, email=username, **extra)

    def test_another_member_is_refused(self) -> None:
        self.client.force_login(self.someone("stranger@example.com"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_the_guardian_may_see_it(self) -> None:
        guardian = self.someone("parent@example.com")
        Player.objects.filter(pk=self.player.pk).update(
            date_of_birth=today() - datetime.timedelta(days=15 * 365)
        )
        Guardianship.objects.create(
            user=guardian, player=self.player, relation=Guardianship.Relation.MO
        )
        self.client.force_login(guardian)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_staff_may_see_it(self) -> None:
        self.client.force_login(self.someone("staff@example.com", is_staff=True))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_the_player_may_see_their_own(self) -> None:
        self.login()
        self.assertEqual(self.client.get(self.url).status_code, 200)
