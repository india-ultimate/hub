import datetime
import itertools
from collections.abc import Sequence
from typing import Any
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from server.season.models import Season
from server.subscription import purchase, refunds
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.transaction.client import razorpay as razorpay_client
from server.transaction.client.razorpay import CLIENT
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

from .test_subscription_model import make_player

ACCEPTED = {"id": "rfnd_123", "status": "processed"}


class TestRefunds(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("m@example.com")
        self.staff = make_player("staff@example.com").user
        self.plans = {
            slug: SubscriptionPlan.objects.get(
                season=self.season, type=SubscriptionType.objects.get(slug=slug)
            )
            for slug in ("regular", "community", "patron")
        }
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_refund",
            payment_id="pay_r",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        self.line = RazorpayTransactionPlayer.objects.create(
            transaction=self.transaction,
            player=self.player,
            plan=self.plans["regular"],
            amount=75000,
        )
        purchase.fulfil(self.transaction)

    def test_a_refund_takes_the_subscription_out_of_use(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="left the sport")

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertIsNotNone(subscription.refunded_at)
        self.assertFalse(subscription.is_active)
        self.assertEqual(Subscription.objects.for_season(self.season).count(), 0)

    def test_the_number_survives_a_refund(self) -> None:
        self.player.refresh_from_db()
        number = self.player.iu_id
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")
        self.player.refresh_from_db()
        self.assertEqual(self.player.iu_id, number)

    def test_refunding_twice_is_refused(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")
            with self.assertRaises(refunds.RefundRefused):
                refunds.refund_line(self.line, by=self.staff, reason="x")

    def test_razorpay_refusing_changes_nothing_here(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            side_effect=Exception("gateway said no"),
        ), self.assertRaises(refunds.RefundRefused):
            refunds.refund_line(self.line, by=self.staff, reason="x")

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertIsNone(subscription.refunded_at)
        self.assertTrue(subscription.is_active)
        self.assertEqual(RazorpayRefund.objects.get().status, RazorpayRefund.Status.FAILED)

    def test_buying_again_after_a_refund_works(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")

        again = RazorpayTransaction.objects.create(
            order_id="order_again2",
            payment_id="pay_a",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=again,
            player=self.player,
            plan=self.plans["regular"],
            amount=75000,
        )
        purchase.fulfil(again)

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.refunded_at)

    def test_reactivating_a_refunded_subscription_at_the_wrong_price_is_flagged(self) -> None:
        # Regular is refunded before an in-flight upgrade to Patron -- priced
        # at just the difference, not Patron's own price -- captures.
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")

        upgrade = RazorpayTransaction.objects.create(
            order_id="order_upgrade_after_refund",
            payment_id="pay_u",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        line = RazorpayTransactionPlayer.objects.create(
            transaction=upgrade,
            player=self.player,
            plan=self.plans["patron"],
            amount=75000,
        )

        purchase.fulfil(upgrade)

        line.refresh_from_db()
        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertTrue(line.needs_review)
        self.assertIsNone(line.subscription)
        self.assertNotEqual(subscription.plan_id, self.plans["patron"].id)
        self.assertNotEqual(subscription.amount_paid, self.plans["patron"].amount)

    def test_a_refunded_line_is_not_applied_again(self) -> None:
        # The nightly sync re-applies every completed order it sees.
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")

        self.transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
        self.transaction.save(update_fields=["status"])
        self.assertEqual(purchase.fulfil(self.transaction), 0)

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertFalse(subscription.is_active)
        self.assertIsNotNone(subscription.refunded_at)

    def test_a_fully_refunded_order_is_marked_refunded(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(self.line, by=self.staff, reason="x")

        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )

    def test_more_than_was_paid_is_refused(self) -> None:
        RazorpayRefund.objects.create(
            transaction=self.transaction,
            amount=75000,
            reason="in the dashboard",
            status=RazorpayRefund.Status.PROCESSED,
            source=RazorpayRefund.Source.RAZORPAY_DASHBOARD,
        )
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ) as gateway, self.assertRaises(refunds.RefundRefused):
            refunds.refund_line(self.line, by=self.staff, reason="x")
        gateway.assert_not_called()

    def test_a_refund_needs_a_reason(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ) as gateway, self.assertRaises(refunds.RefundRefused):
            refunds.refund_line(self.line, by=self.staff, reason="  ")
        gateway.assert_not_called()

    def test_refunding_a_flagged_line_only_clears_the_flag(self) -> None:
        # What Task 9 leaves behind when someone pays twice for a season.
        second = RazorpayTransaction.objects.create(
            order_id="order_twice",
            payment_id="pay_t",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        line = RazorpayTransactionPlayer.objects.create(
            transaction=second,
            player=self.player,
            plan=self.plans["regular"],
            amount=75000,
        )
        purchase.fulfil(second)
        line.refresh_from_db()
        self.assertTrue(line.needs_review)

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(line, by=self.staff, reason="paid twice")

        line.refresh_from_db()
        self.assertFalse(line.needs_review)
        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.refunded_at)
        # And the sync does not hand it over later.
        self.assertEqual(purchase.fulfil(second), 0)

    def test_refunding_an_upgrade_restores_the_earlier_tier(self) -> None:
        community_txn = RazorpayTransaction.objects.create(
            order_id="order_c",
            payment_id="pay_c",
            amount=25000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        Subscription.objects.filter(player=self.player).delete()
        RazorpayTransactionPlayer.objects.create(
            transaction=community_txn,
            player=self.player,
            plan=self.plans["community"],
            amount=25000,
        )
        purchase.fulfil(community_txn)

        upgrade_txn = RazorpayTransaction.objects.create(
            order_id="order_u",
            payment_id="pay_u",
            amount=50000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        upgrade_line = RazorpayTransactionPlayer.objects.create(
            transaction=upgrade_txn,
            player=self.player,
            plan=self.plans["regular"],
            amount=50000,
        )
        purchase.fulfil(upgrade_txn)

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(upgrade_line, by=self.staff, reason="changed mind")

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertEqual(subscription.plan, self.plans["community"])
        self.assertEqual(subscription.amount_paid, 25000)
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.refunded_at)

    def test_the_first_payment_cannot_be_refunded_before_the_upgrade(self) -> None:
        upgrade_txn = RazorpayTransaction.objects.create(
            order_id="order_up2",
            payment_id="pay_u2",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=upgrade_txn,
            player=self.player,
            plan=self.plans["regular"],
            amount=75000,
        )
        # Not a real upgrade path, but it puts a later line on the subscription.
        subscription = Subscription.objects.get(player=self.player, season=self.season)
        RazorpayTransactionPlayer.objects.filter(transaction=upgrade_txn).update(
            subscription=subscription
        )

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ) as gateway, self.assertRaises(refunds.RefundRefused):
            refunds.refund_line(self.line, by=self.staff, reason="x")
        gateway.assert_not_called()

    def test_refunding_a_subscription_completely_unwinds_every_line(self) -> None:
        upgrade_txn = RazorpayTransaction.objects.create(
            order_id="order_u3",
            payment_id="pay_u3",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        subscription = Subscription.objects.get(player=self.player, season=self.season)
        RazorpayTransactionPlayer.objects.create(
            transaction=upgrade_txn,
            player=self.player,
            plan=self.plans["regular"],
            amount=75000,
            subscription=subscription,
        )

        ids = itertools.count()
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            side_effect=lambda *a, **kw: {"id": f"rfnd_{next(ids)}", "status": "processed"},
        ):
            made = refunds.refund_subscription(subscription, by=self.staff, reason="all back")

        self.assertEqual(len(made), 2)
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)
        self.assertIsNotNone(subscription.refunded_at)
        self.assertEqual(subscription.amount_paid, 0)

    def test_an_order_with_no_line_amounts_is_refunded_whole(self) -> None:
        # A team registration: one payment, no per-person price.
        registration = RazorpayTransaction.objects.create(
            order_id="order_team",
            payment_id="pay_team",
            amount=500000,
            currency="INR",
            user=self.player.user,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(transaction=registration, player=self.player)

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            made = refunds.refund_order(registration, by=self.staff, reason="withdrew")

        self.assertEqual([refund.amount for refund in made], [500000])
        registration.refresh_from_db()
        self.assertEqual(registration.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED)
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ), self.assertRaises(refunds.RefundRefused):
            refunds.refund_order(registration, by=self.staff, reason="again")

    def _migrated_upgrade(self, email: str, amount_paid: int) -> tuple[Any, Any]:
        """A row as 0149 leaves it (tier and amount, no line), then a Patron upgrade."""
        regular = self.plans["regular"]
        patron = SubscriptionPlan.objects.get(season=self.season, type__slug="patron")
        player = make_player(email)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=regular,
            amount_paid=amount_paid,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            is_active=True,
            waiver_valid=True,
        )
        upgrade = RazorpayTransaction.objects.create(
            order_id=f"o_{email}",
            payment_id=f"p_{email}",
            amount=patron.amount - amount_paid,
            currency="INR",
            user=player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        line = RazorpayTransactionPlayer.objects.create(
            transaction=upgrade, player=player, plan=patron, amount=patron.amount - amount_paid
        )
        purchase.fulfil(upgrade, notify=False)
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            refunds.refund_line(line, by=self.staff, reason="upgraded by mistake")
        line.refresh_from_db()
        return Subscription.objects.get(player=player, season=self.season), line

    def test_refunding_the_upgrade_of_a_migrated_subscription_keeps_what_they_paid_before(
        self,
    ) -> None:
        subscription, line = self._migrated_upgrade("legacy@example.com", 75000)

        self.assertIsNone(subscription.refunded_at)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.plan, self.plans["regular"])
        self.assertEqual(subscription.amount_paid, 75000)
        self.assertFalse(line.needs_review)

    def test_an_earlier_amount_no_tier_matches_is_left_for_staff(self) -> None:
        # 500 matches no tier in 2026-27.
        subscription, line = self._migrated_upgrade("odd@example.com", 50000)

        self.assertIsNone(subscription.refunded_at)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.plan.type.slug, "patron")
        self.assertEqual(subscription.amount_paid, 50000)
        self.assertTrue(line.needs_review)
        self.assertIn("set it by hand", line.review_note)


class TestRefundSync(TestCase):
    """What `sync_razorpay_transactions` makes of Razorpay's own refunds."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("sync@example.com")
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_sync",
            payment_id="pay_sync",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        self.line = RazorpayTransactionPlayer.objects.create(
            transaction=self.transaction,
            player=self.player,
            plan=SubscriptionPlan.objects.get(season=self.season, type__slug="regular"),
            amount=75000,
        )

    def sync(
        self, entries: list[dict[str, Any]], *args: str, payments: Sequence[dict[str, Any]] = ()
    ) -> None:
        with (
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_transactions",
                return_value=payments,
            ),
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_refunds",
                return_value=entries,
            ),
        ):
            call_command("sync_razorpay_transactions", *args)

    # Razorpay lists newest first: the captured retry, then the failed first try.
    RETRIED = [
        {"id": "pay_sync", "order_id": "order_sync", "status": "captured"},
        {"id": "pay_bad", "order_id": "order_sync", "status": "failed"},
    ]

    def test_a_failed_try_before_a_captured_retry_leaves_the_order_paid(self) -> None:
        for _night in range(2):
            self.sync([], "--no-email", payments=self.RETRIED)
            self.transaction.refresh_from_db()
            self.assertEqual(
                self.transaction.status, RazorpayTransaction.TransactionStatusChoices.COMPLETED
            )

    def test_a_refunded_order_is_never_moved(self) -> None:
        refunded = RazorpayTransaction.TransactionStatusChoices.REFUNDED
        self.transaction.status = refunded
        self.transaction.save(update_fields=["status"])

        for payments in (self.RETRIED, self.RETRIED[1:], self.RETRIED[:1]):
            self.sync([], "--no-email", payments=payments)
            self.transaction.refresh_from_db()
            self.assertEqual(self.transaction.status, refunded)

    def test_a_dashboard_refund_is_recorded_and_flagged(self) -> None:
        self.sync(
            [
                {
                    "id": "rfnd_dash",
                    "payment_id": "pay_sync",
                    "amount": 75000,
                    "status": "processed",
                }
            ]
        )

        refund = RazorpayRefund.objects.get()
        self.assertEqual(refund.source, RazorpayRefund.Source.RAZORPAY_DASHBOARD)
        self.assertEqual(refund.status, RazorpayRefund.Status.PROCESSED)
        self.line.refresh_from_db()
        self.assertTrue(self.line.needs_review)
        # The audit's "refunded but still completed" rows are what this fixes.
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )

    def test_a_hub_refund_that_later_fails_goes_back_to_review(self) -> None:
        RazorpayRefund.objects.create(
            transaction=self.transaction,
            line=self.line,
            amount=75000,
            razorpay_refund_id="rfnd_hub",
            status=RazorpayRefund.Status.PENDING,
            reason="asked for it back",
        )

        self.sync(
            [
                {
                    "id": "rfnd_hub",
                    "payment_id": "pay_sync",
                    "amount": 75000,
                    "status": "failed",
                }
            ]
        )

        refund = RazorpayRefund.objects.get()
        self.assertEqual(refund.status, RazorpayRefund.Status.FAILED)
        self.assertEqual(refund.source, RazorpayRefund.Source.HUB)
        self.line.refresh_from_db()
        self.assertTrue(self.line.needs_review)

    def test_a_pending_hub_refund_settles_the_order_when_it_processes(self) -> None:
        RazorpayRefund.objects.create(
            transaction=self.transaction,
            line=self.line,
            amount=75000,
            razorpay_refund_id="rfnd_hub2",
            status=RazorpayRefund.Status.PENDING,
            reason="asked for it back",
        )

        self.sync(
            [
                {
                    "id": "rfnd_hub2",
                    "payment_id": "pay_sync",
                    "amount": 75000,
                    "status": "processed",
                }
            ]
        )

        self.assertEqual(RazorpayRefund.objects.get().status, RazorpayRefund.Status.PROCESSED)
        self.line.refresh_from_db()
        self.assertFalse(self.line.needs_review)
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )

    def test_syncing_the_same_refund_twice_records_it_once(self) -> None:
        entries = [
            {
                "id": "rfnd_dash",
                "payment_id": "pay_sync",
                "amount": 75000,
                "status": "processed",
            }
        ]
        self.sync(entries, "--since", "2024-08-01")
        self.sync(entries, "--since", "2024-08-01")
        self.assertEqual(RazorpayRefund.objects.count(), 1)

    def test_a_pending_refund_that_fails_puts_the_subscription_back(self) -> None:
        purchase.fulfil(self.transaction)
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            return_value={"id": "rfnd_slow", "status": "pending"},
        ):
            refunds.refund_line(self.line, by=self.player.user, reason="asked for it back")

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertFalse(subscription.is_active)
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )

        self.sync(
            [{"id": "rfnd_slow", "payment_id": "pay_sync", "amount": 75000, "status": "failed"}]
        )

        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.refunded_at)
        self.assertEqual(subscription.amount_paid, 75000)
        self.assertEqual(subscription.plan, self.line.plan)
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.COMPLETED
        )
        self.line.refresh_from_db()
        self.assertTrue(self.line.needs_review)
        self.assertIn("failed at Razorpay", self.line.review_note)

    def test_a_whole_order_refund_that_fails_flags_every_line(self) -> None:
        registration = RazorpayTransaction.objects.create(
            order_id="order_reg",
            payment_id="pay_reg",
            amount=500000,
            currency="INR",
            user=self.player.user,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        other = make_player("teammate@example.com")
        for player in (self.player, other):
            RazorpayTransactionPlayer.objects.create(transaction=registration, player=player)

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            return_value={"id": "rfnd_reg", "status": "pending"},
        ):
            refunds.refund_order(registration, by=self.player.user, reason="withdrew")

        registration.refresh_from_db()
        self.assertEqual(registration.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED)

        self.sync(
            [{"id": "rfnd_reg", "payment_id": "pay_reg", "amount": 500000, "status": "failed"}]
        )

        registration.refresh_from_db()
        self.assertEqual(
            registration.status, RazorpayTransaction.TransactionStatusChoices.COMPLETED
        )
        self.assertEqual(
            RazorpayTransactionPlayer.objects.filter(
                transaction=registration, needs_review=True
            ).count(),
            2,
        )
        # And the order can be refunded afresh, now nothing stands on it.
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            return_value={"id": "rfnd_reg2", "status": "processed"},
        ):
            made = refunds.refund_order(registration, by=None, reason="second try")
        self.assertEqual([refund.amount for refund in made], [500000])

    def test_a_failed_refund_leaves_a_subscription_someone_else_touched(self) -> None:
        purchase.fulfil(self.transaction)
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            return_value={"id": "rfnd_slow2", "status": "pending"},
        ):
            refunds.refund_line(self.line, by=None, reason="asked for it back")

        # The person buys the season anew before the refund fails.
        anew = RazorpayTransaction.objects.create(
            order_id="order_anew",
            payment_id="pay_anew",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=anew, player=self.player, plan=self.line.plan, amount=75000
        )
        purchase.fulfil(anew)

        self.sync(
            [{"id": "rfnd_slow2", "payment_id": "pay_sync", "amount": 75000, "status": "failed"}]
        )

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertEqual(subscription.amount_paid, 75000)  # not counted twice
        self.line.refresh_from_db()
        self.assertIn("by hand", self.line.review_note)


class TestPager(TestCase):
    """`_all_since` is what both Razorpay listings are read through."""

    def pages(self, *counts: int) -> list[dict[str, Any]]:
        return [
            {"count": count, "items": [{"n": f"{page}-{i}"} for i in range(count)]}
            for page, count in enumerate(counts)
        ]

    def test_it_reads_pages_until_an_empty_one(self) -> None:
        with mock.patch.object(CLIENT.payment, "all", side_effect=self.pages(100, 3, 0)) as all_:
            items = razorpay_client.get_transactions()

        self.assertEqual(len(items), 103)
        self.assertEqual([call.args[0]["skip"] for call in all_.call_args_list], [0, 100, 200])

    def test_since_sets_the_window(self) -> None:
        since = datetime.datetime(2024, 8, 1, tzinfo=datetime.timezone.utc)
        with mock.patch.object(CLIENT.refund, "all", side_effect=self.pages(0)) as all_:
            self.assertEqual(razorpay_client.get_refunds(since), [])

        query = all_.call_args.args[0]
        self.assertEqual(query["from"], int(since.timestamp()))
        self.assertGreater(query["to"], query["from"])

    def test_without_since_it_looks_back_a_week(self) -> None:
        with mock.patch.object(CLIENT.refund, "all", side_effect=self.pages(0)) as all_:
            razorpay_client.get_refunds()

        query = all_.call_args.args[0]
        week = int(datetime.timedelta(days=7).total_seconds())
        self.assertEqual(query["to"] - query["from"], week)
