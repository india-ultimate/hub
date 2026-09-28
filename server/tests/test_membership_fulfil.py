from typing import Any
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from server.membership import purchase
from server.membership.models import Membership, MembershipPlan, MembershipType
from server.season.models import Season
from server.task.models import Task
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

from .test_membership_model import make_player


class TestFulfil(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("l@example.com")
        self.plans = {
            slug: MembershipPlan.objects.get(
                season=self.season, type=MembershipType.objects.get(slug=slug)
            )
            for slug in ("regular", "community")
        }

    def order(self, plan: MembershipPlan, amount: int) -> RazorpayTransaction:
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

    def test_a_paid_order_creates_the_membership(self) -> None:
        purchase.fulfil(self.order(self.plans["regular"], 75000))
        membership = Membership.objects.get(player=self.player, season=self.season)
        self.assertTrue(membership.is_active)
        self.assertEqual(membership.amount_paid, 75000)
        self.assertEqual(membership.plan, self.plans["regular"])

    def test_the_player_gets_a_number(self) -> None:
        purchase.fulfil(self.order(self.plans["regular"], 75000))
        self.player.refresh_from_db()
        self.assertTrue((self.player.membership_number or "").startswith("IU-26-"))

    def test_running_twice_changes_nothing(self) -> None:
        transaction = self.order(self.plans["regular"], 75000)
        purchase.fulfil(transaction)
        applied = purchase.fulfil(transaction)
        self.assertEqual(applied, 0)
        self.assertEqual(Membership.objects.filter(player=self.player).count(), 1)

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

        membership = Membership.objects.get(player=self.player, season=self.season)
        self.assertEqual(membership.plan, self.plans["regular"])
        self.assertEqual(membership.amount_paid, 75000)

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
        self.assertEqual(Membership.objects.filter(player=self.player).count(), 1)

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
        self.assertEqual(Membership.objects.count(), 0)


class TestWebhook(TestCase):
    """The webhook is the one fulfilment path whose caller we do not control."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("w@example.com")
        self.plan = MembershipPlan.objects.get(
            season=self.season, type=MembershipType.objects.get(slug="regular")
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
        self.assertEqual(Membership.objects.count(), 0)

    def test_only_a_captured_payment_buys_anything(self) -> None:
        self.assertEqual(self.post("payment.authorized").json()["message"], "Ignored webhook")
        self.assertEqual(Membership.objects.count(), 0)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "created")

    def test_an_order_paid_event_also_completes_the_order(self) -> None:
        self.assertEqual(self.post("order.paid").json()["message"], "Webhook processed")
        self.assertEqual(Membership.objects.filter(player=self.player).count(), 1)

    def test_a_capture_is_only_acted_on_once(self) -> None:
        self.assertEqual(self.post("payment.captured").json()["message"], "Webhook processed")
        self.assertEqual(self.post("payment.captured").json()["message"], "Already processed")
        self.assertEqual(Membership.objects.filter(player=self.player).count(), 1)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 1)

    def test_a_resync_can_apply_payments_without_mailing_anyone(self) -> None:
        # What the launch runbook runs: old payments are handed over, but
        # nobody hears about a membership they have had for a year.
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
        self.assertEqual(Membership.objects.filter(player=self.player).count(), 1)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 0)

    def test_a_refund_is_not_undone_by_a_late_capture(self) -> None:
        self.transaction.status = RazorpayTransaction.TransactionStatusChoices.REFUNDED
        self.transaction.save()
        self.assertEqual(self.post("payment.captured").json()["message"], "Already processed")
        self.transaction.refresh_from_db()
        self.assertEqual(
            self.transaction.status, RazorpayTransaction.TransactionStatusChoices.REFUNDED
        )
        self.assertEqual(Membership.objects.count(), 0)
