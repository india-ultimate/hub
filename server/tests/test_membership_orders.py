import importlib
from typing import Any
from unittest import mock

from django.apps import apps
from django.test import TestCase

from server.membership import pricing, purchase, sponsorship
from server.membership.models import Membership, MembershipPlan, MembershipType
from server.season.models import Season
from server.tests.base import ApiBaseTestCase, fake_order
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

from .test_membership_model import make_player

inflight = importlib.import_module("server.migrations.0155_inflight_orders")


class TestQuote(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("k@example.com")
        self.plans = {
            slug: MembershipPlan.objects.get(
                season=self.season, type=MembershipType.objects.get(slug=slug)
            )
            for slug in ("patron", "regular", "discounted", "community")
        }

    def hold(self, slug: str, paid: int | None, **fields: Any) -> Membership:
        return Membership.objects.create(
            player=self.player,
            season=self.season,
            plan=self.plans[slug],
            amount_paid=paid,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            **{"is_active": True, **fields},
        )

    def test_the_seeded_prices(self) -> None:
        self.assertEqual(
            {slug: plan.amount for slug, plan in self.plans.items()},
            {"patron": 150000, "regular": 75000, "discounted": 30000, "community": 25000},
        )

    def test_a_first_membership_costs_the_full_price(self) -> None:
        quote = pricing.quote(self.player, self.plans["regular"])
        self.assertEqual((quote.kind, quote.amount), ("new", 75000))

    def test_an_upgrade_costs_the_difference(self) -> None:
        self.hold("community", 25000)
        quote = pricing.quote(self.player, self.plans["regular"])
        self.assertEqual((quote.kind, quote.amount), ("upgrade", 50000))

    def test_the_same_tier_again_is_refused(self) -> None:
        self.hold("regular", 75000)
        with self.assertRaises(pricing.NotForSale):
            pricing.quote(self.player, self.plans["regular"])

    def test_a_cheaper_tier_is_refused_as_a_downgrade(self) -> None:
        self.hold("patron", 150000)
        with self.assertRaises(pricing.NotForSale):
            pricing.quote(self.player, self.plans["community"])

    def test_a_cheaper_tier_is_refused_even_when_the_held_one_was_free(self) -> None:
        # Staff give memberships away in admin; that is still a Patron.
        self.hold("patron", None)
        with self.assertRaises(pricing.NotForSale):
            pricing.quote(self.player, self.plans["regular"])

    def test_an_inactive_row_is_bought_over(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.season,
            plan=None,
            is_active=False,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        quote = pricing.quote(self.player, self.plans["regular"])
        self.assertEqual((quote.kind, quote.amount), ("new", 75000))

    def test_a_refunded_row_is_bought_over(self) -> None:
        self.hold("patron", 150000, refunded_at="2026-09-01T00:00:00Z")
        quote = pricing.quote(self.player, self.plans["regular"])
        self.assertEqual((quote.kind, quote.amount), ("new", 75000))

    def test_last_seasons_membership_does_not_count(self) -> None:
        old = Season.objects.get(name="Season 2025-2026")
        Membership.objects.create(
            player=self.player,
            season=old,
            plan=MembershipPlan.objects.get(season=old, type__slug="patron"),
            amount_paid=150000,
            is_active=True,
            start_date=old.start_date,
            end_date=old.end_date,
        )
        quote = pricing.quote(self.player, self.plans["regular"])
        self.assertEqual((quote.kind, quote.amount), ("new", 75000))

    def test_the_discounted_tier_needs_a_grant(self) -> None:
        with self.assertRaises(pricing.NeedsGrant):
            pricing.quote(self.player, self.plans["discounted"])

    def test_the_legacy_sponsored_flag_is_not_a_grant(self) -> None:
        self.player.sponsored = True
        self.player.save()
        with self.assertRaises(pricing.NeedsGrant):
            pricing.quote(self.player, self.plans["discounted"])

    def test_the_discounted_tier_is_allowed_with_a_grant(self) -> None:
        sponsorship.grant(self.player, self.season)
        quote = pricing.quote(self.player, self.plans["discounted"])
        self.assertEqual((quote.kind, quote.amount), ("new", 30000))

    def test_a_grant_for_another_season_does_not_count(self) -> None:
        sponsorship.grant(self.player, Season.objects.get(name="Season 2025-2026"))
        with self.assertRaises(pricing.NeedsGrant):
            pricing.quote(self.player, self.plans["discounted"])

    def test_a_plan_not_on_sale_is_refused(self) -> None:
        old = Season.objects.get(name="Season 2025-2026")
        plan = MembershipPlan.objects.get(
            season=old, type=MembershipType.objects.get(slug="regular")
        )
        with self.assertRaises(pricing.NotForSale):
            pricing.quote(self.player, plan)


class TestOrderValidation(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()
        self.s26 = Season.objects.get(name="Season 2026-2027")

    def post_order(self, items: list[dict[str, Any]], amount: int = 0) -> Any:
        with mock.patch(
            "server.transaction.client.razorpay.create_order", return_value=fake_order(amount)
        ) as create_order:
            response = self.client.post(
                "/api/transactions/razorpay",
                data={"season_id": self.s26.id, "items": items},
                content_type="application/json",
            )
        self.create_order = create_order
        return response

    def test_an_unknown_player_is_refused(self) -> None:
        response = self.post_order([{"player_id": 999999, "plan_type": "regular"}])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["message"], "Some players couldn't be found in the DB: [999999]"
        )
        self.create_order.assert_not_called()

    def test_an_unknown_season_is_refused(self) -> None:
        response = self.client.post(
            "/api/transactions/razorpay",
            data={
                "season_id": 999999,
                "items": [{"player_id": self.player.id, "plan_type": "regular"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["message"], "Season does not exist!")

    def test_an_unknown_tier_is_refused(self) -> None:
        response = self.post_order([{"player_id": self.player.id, "plan_type": "gold"}])
        self.assertEqual(response.status_code, 422)

    def test_the_same_player_twice_is_refused(self) -> None:
        item = {"player_id": self.player.id, "plan_type": "regular"}
        response = self.post_order([item, item])
        self.assertEqual(response.status_code, 422)

    def test_an_empty_order_is_refused(self) -> None:
        self.assertEqual(self.post_order([]).status_code, 422)

    def test_a_client_sent_amount_is_ignored(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.create_order", return_value=fake_order(150000)
        ) as create_order:
            response = self.client.post(
                "/api/transactions/razorpay",
                data={
                    "season_id": self.s26.id,
                    "amount": 100,
                    "items": [{"player_id": self.player.id, "plan_type": "patron", "amount": 100}],
                },
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        create_order.assert_called_once_with(150000, receipt=mock.ANY, notes=mock.ANY)

    def test_the_discounted_tier_without_a_grant_is_refused(self) -> None:
        response = self.post_order([{"player_id": self.player.id, "plan_type": "discounted"}])
        self.assertEqual(response.status_code, 422)
        self.create_order.assert_not_called()

    def test_a_downgrade_is_refused(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            plan=MembershipPlan.objects.get(season=self.s26, type__slug="regular"),
            amount_paid=75000,
            is_active=True,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        response = self.post_order([{"player_id": self.player.id, "plan_type": "community"}])
        self.assertEqual(response.status_code, 422)
        self.assertIn("can only move up a tier", response.json()["message"])

    def test_one_order_is_charged_the_plan_price_and_records_its_line(self) -> None:
        response = self.post_order([{"player_id": self.player.id, "plan_type": "regular"}], 75000)
        self.assertEqual(response.status_code, 200)
        self.create_order.assert_called_once_with(75000, receipt=mock.ANY, notes=mock.ANY)
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual(transaction.season, self.s26)
        self.assertEqual(transaction.start_date, self.s26.start_date)
        self.assertEqual(
            transaction.type, RazorpayTransaction.TransactionTypeChoices.ANNUAL_MEMBERSHIP
        )
        self.assertEqual(
            list(
                RazorpayTransactionPlayer.objects.filter(transaction=transaction).values_list(
                    "player_id", "plan__type__slug", "amount"
                )
            ),
            [(self.player.id, "regular", 75000)],
        )

    def test_a_group_can_mix_tiers(self) -> None:
        coach = make_player("coach@example.com")
        sponsored = make_player("sponsored@example.com")
        sponsorship.grant(sponsored, self.s26)
        response = self.post_order(
            [
                {"player_id": self.player.id, "plan_type": "regular"},
                {"player_id": coach.id, "plan_type": "community"},
                {"player_id": sponsored.id, "plan_type": "discounted"},
            ],
            130000,
        )
        self.assertEqual(response.status_code, 200)
        self.create_order.assert_called_once_with(130000, receipt=mock.ANY, notes=mock.ANY)
        lines = RazorpayTransactionPlayer.objects.filter(transaction_id=response.json()["order_id"])
        self.assertEqual(
            set(lines.values_list("player_id", "plan__type__slug", "amount")),
            {
                (self.player.id, "regular", 75000),
                (coach.id, "community", 25000),
                (sponsored.id, "discounted", 30000),
            },
        )

    def test_an_upgrade_charges_the_difference(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            plan=MembershipPlan.objects.get(season=self.s26, type__slug="community"),
            amount_paid=25000,
            is_active=True,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        response = self.post_order([{"player_id": self.player.id, "plan_type": "patron"}], 125000)
        self.assertEqual(response.status_code, 200)
        self.create_order.assert_called_once_with(125000, receipt=mock.ANY, notes=mock.ANY)

    def test_upgrades_are_bought_one_person_at_a_time(self) -> None:
        Membership.objects.create(
            player=self.player,
            season=self.s26,
            plan=MembershipPlan.objects.get(season=self.s26, type__slug="community"),
            amount_paid=25000,
            is_active=True,
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )
        other = make_player("friend@example.com")
        response = self.post_order(
            [
                {"player_id": self.player.id, "plan_type": "regular"},
                {"player_id": other.id, "plan_type": "regular"},
            ]
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["message"], "Upgrades are bought one person at a time.")

    def test_no_membership_row_is_created_when_the_order_is_placed(self) -> None:
        before = Membership.objects.count()
        response = self.post_order([{"player_id": self.player.id, "plan_type": "regular"}], 75000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Membership.objects.count(), before)

    def test_razorpay_being_down_is_a_502(self) -> None:
        with mock.patch("server.transaction.client.razorpay.create_order", return_value=None):
            response = self.client.post(
                "/api/transactions/razorpay",
                data={
                    "season_id": self.s26.id,
                    "items": [{"player_id": self.player.id, "plan_type": "regular"}],
                },
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 502)
        self.assertFalse(RazorpayTransaction.objects.exists())

    def test_an_event_membership_is_no_longer_a_valid_order(self) -> None:
        response = self.client.post(
            "/api/transactions/razorpay",
            data={"player_id": self.player.id, "event_id": self.event.id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_the_old_annual_body_is_no_longer_a_valid_order(self) -> None:
        response = self.client.post(
            "/api/transactions/razorpay",
            data={"player_id": self.player.id, "season_id": self.s26.id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

    def test_the_phonepe_and_manual_routes_are_gone(self) -> None:
        body = {"season_id": self.s26.id, "items": []}
        for url in ("/api/transactions/phonepe", "/api/transactions/manual/123"):
            response = self.client.post(url, data=body, content_type="application/json")
            self.assertIn(response.status_code, (404, 405), url)


class TestInFlightOrders(TestCase):
    """Orders placed before the deploy, whose lines carry no tier."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("inflight@example.com")

    def order(self, amount: int, status: str, **fields: Any) -> RazorpayTransaction:
        return RazorpayTransaction.objects.create(
            order_id=f"order_old_{amount}_{status}",
            payment_id="",
            amount=amount,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=status,
            **fields,
        )

    def test_an_order_placed_before_the_change_still_lands_when_paid(self) -> None:
        transaction = self.order(75000, RazorpayTransaction.TransactionStatusChoices.PENDING)
        # A line with no plan, exactly as the old checkout left it.
        RazorpayTransactionPlayer.objects.create(transaction=transaction, player=self.player)

        inflight.fill_pending_lines(apps, None)

        line = RazorpayTransactionPlayer.objects.get(transaction=transaction)
        self.assertEqual(
            line.plan, MembershipPlan.objects.get(season=self.season, type__slug="regular")
        )
        self.assertEqual(line.amount, 75000)

        transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
        transaction.save(update_fields=["status"])
        purchase.fulfil(transaction)

        self.assertTrue(Membership.objects.get(player=self.player, season=self.season).is_active)

    def test_an_abandoned_order_is_no_trouble(self) -> None:
        # 927 of these sit in production, most for amounts no tier matches.
        odd = self.order(31337, RazorpayTransaction.TransactionStatusChoices.PENDING)
        RazorpayTransactionPlayer.objects.create(transaction=odd, player=self.player)
        empty = self.order(75000, RazorpayTransaction.TransactionStatusChoices.FAILED)

        inflight.fill_pending_lines(apps, None)

        self.assertIsNone(RazorpayTransactionPlayer.objects.get(transaction=odd).plan)
        self.assertFalse(RazorpayTransactionPlayer.objects.filter(transaction=empty).exists())
        self.assertFalse(Membership.objects.exists())

    def test_the_discounted_rate_still_needs_the_old_sponsored_flag(self) -> None:
        transaction = self.order(25000, RazorpayTransaction.TransactionStatusChoices.PENDING)
        RazorpayTransactionPlayer.objects.create(transaction=transaction, player=self.player)

        inflight.fill_pending_lines(apps, None)

        self.assertIsNone(RazorpayTransactionPlayer.objects.get(transaction=transaction).plan)

    def test_a_group_order_is_left_for_staff(self) -> None:
        # Two people, and a total that happens to be one person's patron
        # price. The old checkout charged for the line set as it was then,
        # which is not necessarily the line set now, so any tier read back
        # from the total would be a guess.
        transaction = self.order(150000, RazorpayTransaction.TransactionStatusChoices.PENDING)
        for email in ("one@example.com", "two@example.com"):
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction, player=make_player(email)
            )

        inflight.fill_pending_lines(apps, None)

        self.assertFalse(
            RazorpayTransactionPlayer.objects.filter(
                transaction=transaction, plan__isnull=False
            ).exists()
        )
