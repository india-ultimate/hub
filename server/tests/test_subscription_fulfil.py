from typing import Any
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from server.core.models import Player
from server.season.models import Season
from server.subscription import numbers, purchase
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.task.models import Task
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

from .test_subscription_model import make_player


class TestFulfil(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("l@example.com")
        self.plans = {
            slug: SubscriptionPlan.objects.get(
                season=self.season, type=SubscriptionType.objects.get(slug=slug)
            )
            for slug in ("regular", "community")
        }

    def order(self, plan: SubscriptionPlan, amount: int) -> RazorpayTransaction:
        transaction = RazorpayTransaction.objects.create(
            order_id=f"order_{plan.type.slug}_{amount}",
            payment_id="pay_x",
            amount=amount,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=transaction, player=self.player, plan=plan, amount=amount
        )
        return transaction

    def test_a_paid_order_creates_the_subscription(self) -> None:
        purchase.fulfil(self.order(self.plans["regular"], 75000))
        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.amount_paid, 75000)
        self.assertEqual(subscription.plan, self.plans["regular"])

    def test_the_player_gets_a_number(self) -> None:
        purchase.fulfil(self.order(self.plans["regular"], 75000))
        self.player.refresh_from_db()
        self.assertTrue((self.player.iu_id or "").startswith("IU-26-"))

    def test_running_twice_changes_nothing(self) -> None:
        transaction = self.order(self.plans["regular"], 75000)
        purchase.fulfil(transaction)
        applied = purchase.fulfil(transaction)
        self.assertEqual(applied, 0)
        self.assertEqual(Subscription.objects.filter(player=self.player).count(), 1)

    def test_an_upgrade_moves_the_tier_and_adds_to_what_was_paid(self) -> None:
        purchase.fulfil(self.order(self.plans["community"], 25000))
        upgrade = RazorpayTransaction.objects.create(
            order_id="order_upgrade",
            payment_id="pay_y",
            amount=50000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=upgrade,
            player=self.player,
            plan=self.plans["regular"],
            amount=50000,
        )
        purchase.fulfil(upgrade)

        subscription = Subscription.objects.get(player=self.player, season=self.season)
        self.assertEqual(subscription.plan, self.plans["regular"])
        self.assertEqual(subscription.amount_paid, 75000)

    def test_paying_twice_for_one_season_flags_the_second(self) -> None:
        purchase.fulfil(self.order(self.plans["regular"], 75000))
        second = RazorpayTransaction.objects.create(
            order_id="order_again",
            payment_id="pay_z",
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
        self.assertEqual(Subscription.objects.filter(player=self.player).count(), 1)

    def test_one_confirmation_email_is_queued(self) -> None:
        transaction = self.order(self.plans["regular"], 75000)
        purchase.fulfil(transaction)
        purchase.fulfil(transaction)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 1)

    def test_a_registration_order_is_left_alone(self) -> None:
        transaction = RazorpayTransaction.objects.create(
            order_id="order_team",
            payment_id="pay_t",
            amount=45000,
            currency="INR",
            user=self.player.user,
            start_date="2026-01-01",
            end_date="2026-01-02",
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(transaction=transaction, player=self.player)
        self.assertEqual(purchase.fulfil(transaction), 0)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_an_unpaid_order_applies_nothing(self) -> None:
        transaction = self.order(self.plans["regular"], 75000)
        transaction.status = "created"
        transaction.save(update_fields=["status"])
        self.assertEqual(purchase.fulfil(transaction), 0)
        self.assertFalse(Subscription.objects.exists())

    def test_a_line_that_loses_a_race_is_flagged_and_the_rest_applied(self) -> None:
        """Another order creates this season's subscription between fulfil's
        read and its insert. The unique (player, season) refuses the insert;
        that line goes to staff, and the other person still gets theirs."""
        friend = make_player("friend@example.com")
        transaction = self.order(self.plans["regular"], 75000)
        RazorpayTransactionPlayer.objects.create(
            transaction=transaction, player=friend, plan=self.plans["regular"], amount=75000
        )
        winner = Subscription.objects.create(
            player=self.player,
            season=self.season,
            plan=self.plans["community"],
            amount_paid=25000,
            is_active=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        read = Subscription.objects.filter

        def before_the_race(**lookups: Any) -> Any:
            # What fulfil read before the other order committed.
            if lookups.get("player_id") == self.player.id:
                return Subscription.objects.none()
            return read(**lookups)

        with mock.patch.object(Subscription.objects, "filter", side_effect=before_the_race):
            applied = purchase.fulfil(transaction, notify=False)

        self.assertEqual(applied, 1)
        lost = RazorpayTransactionPlayer.objects.get(transaction=transaction, player=self.player)
        self.assertTrue(lost.needs_review)
        self.assertIn("another payment created", lost.review_note)
        self.assertIsNone(lost.subscription)
        winner.refresh_from_db()
        self.assertEqual((winner.plan, winner.amount_paid), (self.plans["community"], 25000))
        self.assertTrue(Subscription.objects.get(player=friend, season=self.season).is_active)

    def test_running_out_of_numbers_flags_the_line(self) -> None:
        # Someone already holds the one number every attempt picks.
        make_player("holder@example.com")
        Player.objects.filter(user__email="holder@example.com").update(iu_id="IU-26-0001")
        transaction = self.order(self.plans["regular"], 75000)

        with mock.patch(
            "server.subscription.numbers.next_position", return_value=1
        ) as next_position:
            applied = purchase.fulfil(transaction, notify=False)

        self.assertEqual(next_position.call_count, numbers.RETRIES)
        self.assertEqual(applied, 0)
        line = RazorpayTransactionPlayer.objects.get(transaction=transaction)
        self.assertTrue(line.needs_review)
        self.assertIn("no IU ID could be allocated", line.review_note)
        # The savepoint took the half-made subscription back with it.
        self.assertFalse(Subscription.objects.filter(player=self.player).exists())
        self.player.refresh_from_db()
        self.assertIsNone(self.player.iu_id)

    def test_assign_number_gives_up_after_its_retries(self) -> None:
        make_player("holder@example.com")
        Player.objects.filter(user__email="holder@example.com").update(iu_id="IU-26-0001")
        with mock.patch(
            "server.subscription.numbers.next_position", return_value=1
        ), self.assertRaises(IntegrityError):
            numbers.assign_number(self.player, self.season)
        self.assertIsNone(self.player.iu_id)


class TestWebhook(TestCase):
    """The webhook is the one fulfilment path whose caller we do not control."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("w@example.com")
        self.plan = SubscriptionPlan.objects.get(
            season=self.season, type=SubscriptionType.objects.get(slug="regular")
        )
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_hook",
            payment_id="",
            # As production stores an unpaid order: Razorpay's status, saved as-is.
            status="created",
            amount=self.plan.amount,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=self.transaction,
            player=self.player,
            plan=self.plan,
            amount=self.plan.amount,
        )

    def post(self, event: str) -> Any:
        body = {
            "event": event,
            "payload": {"payment": {"entity": {"id": "pay_hook", "order_id": "order_hook"}}},
        }
        with mock.patch(
            "server.transaction.client.razorpay.verify_webhook_payload", return_value=True
        ):
            return self.client.post(
                "/api/transactions/razorpay/webhook",
                data=body,
                content_type="application/json",
            )

    def test_an_unsigned_webhook_changes_nothing(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.verify_webhook_payload", return_value=False
        ):
            response = self.client.post(
                "/api/transactions/razorpay/webhook",
                data={"event": "payment.captured"},
                content_type="application/json",
            )
        self.assertEqual(response.json()["message"], "Signature could not be verified")
        self.assertEqual(Subscription.objects.count(), 0)

    def test_only_a_captured_payment_buys_anything(self) -> None:
        self.assertEqual(self.post("payment.authorized").json()["message"], "Ignored webhook")
        self.assertEqual(Subscription.objects.count(), 0)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "created")

    def test_an_order_paid_event_also_completes_the_order(self) -> None:
        self.assertEqual(self.post("order.paid").json()["message"], "Webhook processed")
        self.assertEqual(Subscription.objects.filter(player=self.player).count(), 1)

    def test_a_capture_is_only_acted_on_once(self) -> None:
        self.assertEqual(self.post("payment.captured").json()["message"], "Webhook processed")
        self.assertEqual(self.post("payment.captured").json()["message"], "Already processed")
        self.assertEqual(Subscription.objects.filter(player=self.player).count(), 1)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 1)

    def test_a_resync_can_apply_payments_without_mailing_anyone(self) -> None:
        # What the launch runbook runs: old payments are handed over, but
        # nobody hears about a subscription they have had for a year.
        with (
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_transactions",
                return_value=[{"status": "captured", "order_id": "order_hook"}],
            ),
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_refunds",
                return_value=[],
            ),
        ):
            call_command("sync_razorpay_transactions", "--no-email")

        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.COMPLETED
        )
        self.assertEqual(Subscription.objects.filter(player=self.player).count(), 1)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 0)

    def test_a_refund_is_not_undone_by_a_late_capture(self) -> None:
        self.transaction.status = RazorpayTransaction.TransactionStatusChoices.REFUNDED
        self.transaction.save()
        self.assertEqual(self.post("payment.captured").json()["message"], "Already processed")
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )
        self.assertEqual(Subscription.objects.count(), 0)
