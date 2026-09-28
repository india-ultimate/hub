import datetime
from importlib import import_module
from io import StringIO

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

from server.receipts.models import Receipt, ReceiptSequence
from server.season.models import Season
from server.subscription.models import SubscriptionPlan
from server.task.models import Task
from server.transaction.models import RazorpayRefund, RazorpayTransaction, RazorpayTransactionPlayer

from .test_subscription_model import make_player

migration = import_module("server.migrations.0159_backfill_receipts")
UTC = datetime.timezone.utc


class TestBackfill(TestCase):
    def setUp(self) -> None:
        self.payer = make_player("payer@example.com")
        self.season = Season.objects.get(name="Season 2025-2026")

    def old_order(
        self, order_id: str, paid: datetime.datetime, amount: int, *emails: str, **extra: object
    ) -> RazorpayTransaction:
        transaction = RazorpayTransaction.objects.create(
            order_id=order_id,
            payment_id=f"pay_{order_id}",
            amount=amount,
            currency="INR",
            user=self.payer.user,
            status="completed",
            season=self.season,
            **extra,
        )
        # payment_date is auto_now_add; set the historical date directly.
        RazorpayTransaction.objects.filter(pk=order_id).update(payment_date=paid)
        for email in emails:  # lines as old orders had them: no plan, no amount
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction, player=make_player(email)
            )
        return transaction

    def test_past_orders_are_numbered_in_payment_order_per_year(self) -> None:
        self.old_order("o_b", datetime.datetime(2025, 9, 2, tzinfo=UTC), 70000, "b@x.com")
        self.old_order("o_a", datetime.datetime(2024, 8, 22, tzinfo=UTC), 70000, "a@x.com")
        self.old_order(
            "o_c", datetime.datetime(2025, 8, 30, tzinfo=UTC), 140000, "c@x.com", "d@x.com"
        )
        self.old_order(
            "o_team", datetime.datetime(2025, 8, 30, tzinfo=UTC), 50000, "t@x.com", type="team-reg"
        )

        migration.backfill(apps, None)

        numbers = dict(Receipt.objects.values_list("order_id", "number"))
        self.assertEqual(
            numbers,
            {"o_a": "IU/2024-25/00001", "o_c": "IU/2025-26/00001", "o_b": "IU/2025-26/00002"},
        )
        group = Receipt.objects.get(order_id="o_c")
        self.assertEqual(group.issued_at, datetime.datetime(2025, 8, 30, tzinfo=UTC))
        [row] = group.lines
        self.assertEqual(row["particulars"], "Subscription, Season 2025-2026")
        self.assertEqual((row["quantity"], row["rate"], row["amount"]), (2, 70000, 140000))
        self.assertEqual(len(row["people"]), 2)
        self.assertFalse(Task.objects.exists())  # no email

    def test_processed_refunds_get_notes_and_a_rerun_adds_nothing(self) -> None:
        order = self.old_order("o_r", datetime.datetime(2025, 9, 1, tzinfo=UTC), 70000, "r@x.com")
        RazorpayRefund.objects.create(
            transaction=order,
            amount=70000,
            reason="x",
            status="processed",
            razorpay_refund_id="rfnd_old",
        )
        RazorpayRefund.objects.create(transaction=order, amount=100, reason="x", status="failed")

        migration.backfill(apps, None)
        migration.backfill(apps, None)

        self.assertEqual(Receipt.objects.filter(kind="receipt").count(), 1)
        note = Receipt.objects.get(kind="refund")
        self.assertEqual(note.reference, "rfnd_old")
        original = Receipt.objects.get(kind="receipt")
        self.assertEqual(note.original, original)
        self.assertEqual(note.lines[0]["particulars"], f"Refund against receipt {original.number}")

    def test_a_live_payment_after_the_backfill_takes_the_next_number(self) -> None:
        from server.receipts.issue import next_number

        self.old_order("o_1", datetime.datetime(2026, 9, 1, tzinfo=UTC), 75000, "one@x.com")
        migration.backfill(apps, None)
        self.assertEqual(
            next_number("IU", datetime.datetime(2026, 9, 2, tzinfo=UTC))[0], "IU/2026-27/00002"
        )

    def new_order(
        self,
        order_id: str,
        *lines: tuple[str, str, int],
        status: str = "completed",
    ) -> tuple[RazorpayTransaction, list[RazorpayTransactionPlayer]]:
        """An order as they are now: lines of (email, tier slug, amount)."""
        season = Season.objects.get(name="Season 2026-2027")
        transaction = RazorpayTransaction.objects.create(
            order_id=order_id,
            payment_id=f"pay_{order_id}",
            amount=sum(amount for _, _, amount in lines),
            currency="INR",
            user=self.payer.user,
            status=status,
            season=season,
        )
        RazorpayTransaction.objects.filter(pk=order_id).update(
            payment_date=datetime.datetime(2026, 9, 1, tzinfo=UTC)
        )
        made = [
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction,
                player=make_player(email),
                plan=SubscriptionPlan.objects.get(season=season, type__slug=slug),
                amount=amount,
            )
            for email, slug, amount in lines
        ]
        return transaction, made

    def tier(self, slug: str) -> SubscriptionPlan:
        return SubscriptionPlan.objects.get(season__name="Season 2026-2027", type__slug=slug)

    def test_a_new_style_order_is_grouped_and_an_upgrade_is_named(self) -> None:
        regular, patron = self.tier("regular"), self.tier("patron")
        upgrade = patron.amount - regular.amount
        _, lines = self.new_order(
            "o_new",
            ("r1@x.com", "regular", regular.amount),
            ("r2@x.com", "regular", regular.amount),
            ("up@x.com", "patron", upgrade),
        )

        migration.backfill(apps, None)

        receipt = Receipt.objects.get(order_id="o_new")
        by_particulars = {row["particulars"]: row for row in receipt.lines}
        self.assertEqual(len(by_particulars), 2)
        plain = by_particulars[f"{regular.type.name}, Season 2026-2027"]
        self.assertEqual((plain["quantity"], plain["rate"]), (2, regular.amount))
        self.assertEqual(plain["line_ids"], [lines[0].id, lines[1].id])
        bumped = by_particulars[f"Upgrade to {patron.type.name}, Season 2026-2027"]
        self.assertEqual((bumped["quantity"], bumped["rate"]), (1, upgrade))
        self.assertEqual(bumped["line_ids"], [lines[2].id])
        self.assertEqual(receipt.total, 2 * regular.amount + upgrade)

    def test_a_processed_line_refund_names_that_person(self) -> None:
        regular = self.tier("regular")
        order, lines = self.new_order(
            "o_line",
            ("l1@x.com", "regular", regular.amount),
            ("l2@x.com", "regular", regular.amount),
        )
        RazorpayRefund.objects.create(
            transaction=order,
            line=lines[1],
            amount=regular.amount,
            reason="x",
            status="processed",
            razorpay_refund_id="rfnd_line",
        )

        migration.backfill(apps, None)

        receipt = Receipt.objects.get(kind="receipt")
        note = Receipt.objects.get(kind="refund")
        [row] = receipt.lines
        [line] = note.lines
        self.assertEqual(line["particulars"], f"Refund: {row['particulars']}")
        self.assertEqual(line["people"], [row["people"][1]])  # matched by line id

    def test_only_paid_subscription_orders_get_a_receipt(self) -> None:
        regular = self.tier("regular")
        for status in ("created", "failed", "refunded"):
            self.new_order(
                f"o_{status}", (f"{status}@x.com", "regular", regular.amount), status=status
            )

        migration.backfill(apps, None)

        self.assertEqual(list(Receipt.objects.values_list("order_id", flat=True)), ["o_refunded"])

    def test_reverse_deletes_receipts_and_their_refund_notes(self) -> None:
        order = self.old_order("o_n", datetime.datetime(2025, 9, 1, tzinfo=UTC), 70000, "n@x.com")
        RazorpayRefund.objects.create(
            transaction=order, amount=70000, reason="x", status="processed"
        )
        migration.backfill(apps, None)
        self.assertEqual(Receipt.objects.filter(kind="refund").count(), 1)

        migration.unbackfill(apps, None)

        self.assertFalse(Receipt.objects.exists())
        self.assertFalse(ReceiptSequence.objects.exists())

    def test_the_command_issues_a_receipt_the_release_missed(self) -> None:
        """An order the old release captured after 0159 took its snapshot is
        already settled, so no callback, webhook or nightly sync will ever
        give it a receipt. Running the backfill again is what does."""
        self.old_order("o_late", datetime.datetime(2025, 9, 3, tzinfo=UTC), 70000, "late@x.com")
        first, again = StringIO(), StringIO()

        call_command("issue_missing_receipts", stdout=first)
        call_command("issue_missing_receipts", stdout=again)

        self.assertEqual(Receipt.objects.get(order_id="o_late").number, "IU/2025-26/00001")
        self.assertIn("Issued 1 receipts and 0 refund notes.", first.getvalue())
        self.assertIn("Issued 0 receipts and 0 refund notes.", again.getvalue())
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertFalse(Task.objects.exists())  # no email

    def test_reverse_removes_what_it_made(self) -> None:
        self.old_order("o_x", datetime.datetime(2025, 9, 1, tzinfo=UTC), 70000, "x@x.com")
        migration.backfill(apps, None)
        migration.unbackfill(apps, None)
        self.assertFalse(Receipt.objects.exists())
