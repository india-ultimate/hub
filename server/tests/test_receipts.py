import datetime
import io
from typing import Any
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.db import transaction as db_transaction
from django.test import TestCase

from server.core.models import Player
from server.receipts import rows
from server.receipts.issue import issue_receipt, issue_refund_note, next_number
from server.receipts.models import Receipt, ReceiptSequence
from server.season.models import Season
from server.subscription import purchase
from server.subscription.models import Subscription, SubscriptionPlan
from server.task.models import Task
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

from .test_subscription_model import make_player

UTC = datetime.timezone.utc
COMPLETED = RazorpayTransaction.TransactionStatusChoices.COMPLETED


def plan(slug: str, season: Season) -> SubscriptionPlan:
    return SubscriptionPlan.objects.get(season=season, type__slug=slug)


class ReceiptTestCase(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.payer = make_player("payer@example.com")
        self.payer.user.first_name, self.payer.user.last_name = "Priya", "Rao"
        self.payer.user.phone = "+919845012345"
        self.payer.user.save()
        self.n = 0

    def order(
        self, *lines: tuple[Player, SubscriptionPlan | None, int], **extra: object
    ) -> RazorpayTransaction:
        """lines: (player, plan, amount); the order total is their sum."""
        self.n += 1
        transaction = RazorpayTransaction.objects.create(
            order_id=f"order_{self.n}",
            payment_id=f"pay_{self.n}",
            amount=sum(amount for _, _, amount in lines),
            currency="INR",
            user=self.payer.user,
            season=self.season,
            status=COMPLETED,
            **extra,
        )
        for player, tier, amount in lines:
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction, player=player, plan=tier, amount=amount
            )
        return transaction


class TestRows(TestCase):
    def test_the_same_item_at_the_same_price_is_one_row(self) -> None:
        grouped = rows.group(
            [
                ("Regular Subscription, Season 2026-2027", "Asha Rao (IU-26-0042)", 75000, 11),
                ("Regular Subscription, Season 2026-2027", "Meera Rao (IU-26-0043)", 75000, 12),
                (
                    "Upgrade from Regular to Patron Subscription, Season 2026-2027",
                    "Arjun",
                    75000,
                    13,
                ),
                (
                    "Upgrade from Community to Patron Subscription, Season 2026-2027",
                    "Ravi",
                    125000,
                    14,
                ),
            ]
        )
        self.assertEqual(
            [(r["particulars"][:25], r["quantity"], r["rate"], r["amount"]) for r in grouped],
            [
                ("Regular Subscription, Sea", 2, 75000, 150000),
                ("Upgrade from Regular to P", 1, 75000, 75000),
                ("Upgrade from Community to", 1, 125000, 125000),
            ],
        )
        self.assertEqual(grouped[0]["people"], ["Asha Rao (IU-26-0042)", "Meera Rao (IU-26-0043)"])
        self.assertEqual(grouped[0]["line_ids"], [11, 12])
        self.assertNotIn("line_ids", rows.legacy_row(None, ["A"], 100))

    def test_a_legacy_order_is_one_row_with_a_rate_only_when_it_divides(self) -> None:
        even = rows.legacy_row("Season 2025-2026", ["A", "B"], 140000)
        self.assertEqual((even["quantity"], even["rate"], even["amount"]), (2, 70000, 140000))
        self.assertEqual(even["particulars"], "Subscription, Season 2025-2026")
        odd = rows.legacy_row(None, ["A", "B", "C"], 100000)
        self.assertEqual((odd["quantity"], odd["rate"]), (3, None))
        self.assertEqual(odd["particulars"], "Subscription")

    def test_summary_and_labels(self) -> None:
        grouped = rows.group(
            [
                ("Regular Subscription, Season 2026-2027", "A", 75000, 1),
                ("Regular Subscription, Season 2026-2027", "B", 75000, 2),
                ("Upgrade from Regular to Patron Subscription, Season 2026-2027", "C", 75000, 3),
            ]
        )
        self.assertEqual(
            rows.summary(grouped),
            "Regular Subscription × 2, Upgrade from Regular to Patron Subscription × 1"  # noqa: RUF001
            " — Season 2026-2027",
        )
        self.assertEqual(
            rows.person_label("Asha", "Rao", "a@x", "IU-26-0042"), "Asha Rao (IU-26-0042)"
        )
        self.assertEqual(rows.person_label("", "", "a@x", None), "a@x")


class TestNumbering(TestCase):
    def test_each_series_counts_its_own_year(self) -> None:
        april = datetime.datetime(2026, 4, 2, tzinfo=UTC)
        march = datetime.datetime(2026, 3, 30, tzinfo=UTC)
        self.assertEqual(next_number("IU", april)[0], "IU/2026-27/00001")
        self.assertEqual(next_number("IU", april)[0], "IU/2026-27/00002")
        self.assertEqual(next_number("RF", april)[0], "RF/2026-27/00001")
        self.assertEqual(next_number("IU", march)[0], "IU/2025-26/00001")
        self.assertEqual(len("IU/2026-27/00001"), 16)

    def test_a_number_outside_a_transaction_is_refused(self) -> None:
        # TestCase itself runs inside a transaction, so pretend there is none.
        connection = mock.Mock(in_atomic_block=False)
        with (
            mock.patch.object(db_transaction, "get_connection", return_value=connection),
            self.assertRaisesMessage(RuntimeError, "transaction.atomic()"),
        ):
            next_number("IU", datetime.datetime(2026, 9, 1, tzinfo=UTC))
        self.assertFalse(ReceiptSequence.objects.exists())

    def test_a_rolled_back_number_is_reused(self) -> None:
        when = datetime.datetime(2026, 9, 1, tzinfo=UTC)
        try:
            with db_transaction.atomic():
                next_number("IU", when)
                raise RuntimeError("the capture failed")
        except RuntimeError:
            pass
        self.assertEqual(next_number("IU", when)[0], "IU/2026-27/00001")


class TestIssuing(ReceiptTestCase):
    def test_a_paid_order_gets_a_receipt_with_its_lines(self) -> None:
        asha, meera = make_player("asha@example.com"), make_player("meera@example.com")
        transaction = self.order(
            (asha, plan("regular", self.season), 75000),
            (meera, plan("regular", self.season), 75000),
        )
        purchase.fulfil(transaction)
        receipt = Receipt.objects.get(transaction=transaction, kind=Receipt.Kind.RECEIPT)
        self.assertRegex(receipt.number, r"^IU/\d{4}-\d{2}/\d{5}$")
        self.assertEqual(receipt.total, 150000)
        self.assertEqual(receipt.payer_name, "Priya Rao")
        self.assertEqual(receipt.payer_phone, "+919845012345")
        self.assertEqual(receipt.reference, transaction.payment_id)
        [row] = receipt.lines
        self.assertEqual(row["particulars"], "Regular Subscription, Season 2026-2027")
        self.assertEqual((row["quantity"], row["rate"], row["amount"]), (2, 75000, 150000))
        self.assertEqual(
            row["line_ids"],
            list(
                RazorpayTransactionPlayer.objects.filter(transaction=transaction)
                .order_by("id")
                .values_list("id", flat=True)
            ),
        )

    def test_an_upgrade_names_both_tiers(self) -> None:
        player = make_player("up@example.com")
        purchase.fulfil(self.order((player, plan("regular", self.season), 75000)))
        upgrade = self.order((player, plan("patron", self.season), 75000))
        purchase.fulfil(upgrade)
        [row] = Receipt.objects.get(transaction=upgrade).lines
        self.assertEqual(
            row["particulars"], "Upgrade from Regular to Patron Subscription, Season 2026-2027"
        )
        self.assertEqual(row["amount"], 75000)

    def test_a_line_flagged_for_review_is_still_on_the_receipt(self) -> None:
        player = make_player("twice@example.com")
        purchase.fulfil(self.order((player, plan("regular", self.season), 75000)))
        again = self.order((player, plan("regular", self.season), 75000))
        purchase.fulfil(again)
        self.assertTrue(RazorpayTransactionPlayer.objects.get(transaction=again).needs_review)
        self.assertEqual(Receipt.objects.get(transaction=again).total, 75000)

    def test_callback_webhook_and_sync_make_one_receipt(self) -> None:
        transaction = self.order(
            (make_player("x@example.com"), plan("regular", self.season), 75000)
        )
        for _ in range(3):
            purchase.fulfil(transaction)
        self.assertEqual(Receipt.objects.filter(transaction=transaction).count(), 1)

    def test_no_receipt_for_other_payments_or_unpaid_orders(self) -> None:
        team = self.order((make_player("t@example.com"), None, 50000), type="team-reg")
        self.assertIsNone(issue_receipt(team))
        unpaid = self.order((make_player("u@example.com"), plan("regular", self.season), 75000))
        unpaid.status = "created"
        unpaid.save()
        purchase.fulfil(unpaid)
        self.assertFalse(Receipt.objects.exists())

    def test_a_first_time_player_prints_their_new_iu_id(self) -> None:
        newcomer = make_player("new@example.com")
        self.assertIsNone(newcomer.iu_id)
        transaction = self.order((newcomer, plan("regular", self.season), 75000))
        purchase.fulfil(transaction)
        newcomer.refresh_from_db()
        self.assertIsNotNone(newcomer.iu_id)
        [label] = Receipt.objects.get(transaction=transaction).lines[0]["people"]
        self.assertTrue(label.endswith(f"({newcomer.iu_id})"), label)

    def test_renaming_the_player_later_changes_nothing(self) -> None:
        asha = make_player("asha2@example.com")
        asha.user.first_name, asha.user.last_name = "Asha", "Rao"
        asha.user.save()
        transaction = self.order((asha, plan("regular", self.season), 75000))
        purchase.fulfil(transaction)
        asha.user.first_name = "Renamed"
        asha.user.save()
        receipt = Receipt.objects.get(transaction=transaction)
        self.assertTrue(receipt.lines[0]["people"][0].startswith("Asha Rao"))

    def test_a_failed_capture_leaves_no_gap(self) -> None:
        first = self.order((make_player("f1@example.com"), plan("regular", self.season), 75000))
        with mock.patch(
            "server.subscription.purchase._apply", side_effect=RuntimeError
        ), self.assertRaises(RuntimeError):
            purchase.fulfil(first)
        self.assertFalse(Receipt.objects.exists())
        purchase.fulfil(first)
        self.assertTrue(Receipt.objects.get().number.endswith("/00001"))
        self.assertEqual(ReceiptSequence.objects.get(series="IU").last, 1)


PROCESSED = RazorpayRefund.Status.PROCESSED


class TestRefundNotes(ReceiptTestCase):
    def paid(self, *people: str) -> RazorpayTransaction:
        transaction = self.order(
            *[(make_player(p), plan("regular", self.season), 75000) for p in people]
        )
        purchase.fulfil(transaction)
        return transaction

    def note(self, refund: RazorpayRefund) -> Receipt:
        note = issue_refund_note(refund)
        assert note is not None  # noqa: S101 - for mypy; the tests below check the value
        return note

    def refund(
        self,
        transaction: RazorpayTransaction,
        line: RazorpayTransactionPlayer | None = None,
        **extra: object,
    ) -> RazorpayRefund:
        return RazorpayRefund.objects.create(
            transaction=transaction, line=line, amount=75000, reason="staff only", **extra
        )

    def test_a_processed_line_refund_gets_a_note_against_the_receipt(self) -> None:
        transaction = self.paid("r1@example.com", "r2@example.com")
        line = RazorpayTransactionPlayer.objects.filter(transaction=transaction).first()
        note = self.note(
            self.refund(transaction, line, status=PROCESSED, razorpay_refund_id="rfnd_1")
        )
        receipt = Receipt.objects.get(transaction=transaction, kind=Receipt.Kind.RECEIPT)
        self.assertEqual(note.kind, Receipt.Kind.REFUND)
        self.assertRegex(note.number, r"^RF/\d{4}-\d{2}/00001$")
        self.assertEqual(note.original, receipt)
        self.assertEqual(note.reference, "rfnd_1")
        [row] = note.lines
        self.assertEqual(row["particulars"], "Refund: Regular Subscription, Season 2026-2027")
        self.assertEqual((row["quantity"], row["amount"]), (1, 75000))
        self.assertEqual(len(row["people"]), 1)
        # The receipt already carries the IU ID, so the note repeats it exactly.
        self.assertRegex(row["people"][0], r"\(IU-\d{2}-\d+\)$")
        self.assertIn(row["people"][0], receipt.lines[0]["people"])
        self.assertNotIn("staff only", str(note.lines))
        # The receipt itself is untouched.
        self.assertEqual(Receipt.objects.get(pk=receipt.pk).total, 150000)

    def test_a_renamed_player_still_reads_as_the_receipt_printed_them(self) -> None:
        transaction = self.paid("ren1@example.com", "ren2@example.com")
        line = RazorpayTransactionPlayer.objects.filter(transaction=transaction).first()
        assert line is not None  # noqa: S101 - for mypy
        receipt = Receipt.objects.get(transaction=transaction, kind=Receipt.Kind.RECEIPT)
        frozen = receipt.lines[0]["people"][0]
        line.player.user.first_name = "Renamed"
        line.player.user.save()
        note = self.note(self.refund(transaction, line, status=PROCESSED))
        [row] = note.lines
        self.assertEqual(row["particulars"], "Refund: Regular Subscription, Season 2026-2027")
        self.assertEqual(row["people"], [frozen])
        self.assertNotIn("Renamed", frozen)

    def test_a_whole_order_or_dashboard_refund_reads_against_the_receipt(self) -> None:
        transaction = self.paid("w@example.com")
        note = self.note(self.refund(transaction, status=PROCESSED))
        receipt = Receipt.objects.get(transaction=transaction, kind=Receipt.Kind.RECEIPT)
        self.assertEqual(note.lines[0]["particulars"], f"Refund against receipt {receipt.number}")

    def test_a_pending_refund_gets_no_note_until_processed(self) -> None:
        refund = self.refund(self.paid("p@example.com"), status=RazorpayRefund.Status.PENDING)
        self.assertIsNone(issue_refund_note(refund))
        refund.status = PROCESSED
        refund.save()
        first = self.note(refund)
        self.assertEqual(self.note(refund).pk, first.pk)
        self.assertEqual(Receipt.objects.get(refund=refund).pk, first.pk)

    def test_a_refund_that_fails_gets_no_note(self) -> None:
        refund = self.refund(self.paid("f@example.com"), status=RazorpayRefund.Status.FAILED)
        self.assertIsNone(issue_refund_note(refund))
        self.assertFalse(Receipt.objects.filter(kind=Receipt.Kind.REFUND).exists())

    def test_no_note_for_an_order_without_a_receipt(self) -> None:
        team = self.order((make_player("tm@example.com"), None, 75000), type="team-reg")
        self.assertIsNone(issue_refund_note(self.refund(team, status=PROCESSED)))

    def test_the_sync_notes_a_refund_when_it_turns_processed(self) -> None:
        from server.management.commands.sync_razorpay_transactions import Command

        transaction = self.paid("s@example.com")
        refund = self.refund(
            transaction, status=RazorpayRefund.Status.PENDING, razorpay_refund_id="rfnd_s"
        )
        entry = {
            "id": "rfnd_s",
            "status": "processed",
            "payment_id": transaction.payment_id,
            "amount": 75000,
        }
        with mock.patch(
            "server.management.commands.sync_razorpay_transactions.get_refunds",
            return_value=[entry],
        ):
            Command().sync_refunds(None)
        self.assertTrue(Receipt.objects.filter(refund=refund).exists())

    def test_a_failed_note_in_the_sync_is_reported_and_retried(self) -> None:
        from server.management.commands.sync_razorpay_transactions import Command

        transaction = self.paid("retry@example.com")
        refund = self.refund(
            transaction, status=RazorpayRefund.Status.PENDING, razorpay_refund_id="rfnd_retry"
        )
        entry = {
            "id": "rfnd_retry",
            "status": "processed",
            "payment_id": transaction.payment_id,
            "amount": 75000,
        }
        target = "server.management.commands.sync_razorpay_transactions"
        errors = io.StringIO()
        with (
            mock.patch(f"{target}.get_refunds", return_value=[entry]),
            mock.patch(f"{target}.issue_refund_note", side_effect=RuntimeError("no number")),
        ):
            result = Command(stderr=errors).sync_refunds(None)
        self.assertEqual(result, (0, 1))
        self.assertIn("rfnd_retry", errors.getvalue())
        self.assertIn("no number", errors.getvalue())
        # The status change went with the failed note, so the next sync sees it again.
        refund.refresh_from_db()
        self.assertEqual(refund.status, RazorpayRefund.Status.PENDING)
        self.assertFalse(Receipt.objects.filter(refund=refund).exists())
        with mock.patch(f"{target}.get_refunds", return_value=[entry]):
            self.assertEqual(Command().sync_refunds(None), (1, 0))
        refund.refresh_from_db()
        self.assertEqual(refund.status, PROCESSED)
        self.assertTrue(Receipt.objects.filter(refund=refund).exists())

    def test_one_bad_refund_does_not_stop_the_rest_of_the_sync(self) -> None:
        from server.management.commands.sync_razorpay_transactions import Command

        first_order, second_order = self.paid("one@example.com"), self.paid("two@example.com")
        first = self.refund(
            first_order, status=RazorpayRefund.Status.PENDING, razorpay_refund_id="rfnd_bad"
        )
        second = self.refund(
            second_order, status=RazorpayRefund.Status.PENDING, razorpay_refund_id="rfnd_good"
        )
        entries = [
            {
                "id": r.razorpay_refund_id,
                "status": "processed",
                "payment_id": r.transaction.payment_id,
                "amount": 75000,
            }
            for r in (first, second)
        ]

        def note(refund: RazorpayRefund, notify: bool = True) -> Receipt | None:
            if refund.pk == first.pk:
                raise RuntimeError("no number")
            return issue_refund_note(refund, notify=notify)

        target = "server.management.commands.sync_razorpay_transactions"
        with (
            mock.patch(f"{target}.get_refunds", return_value=entries),
            mock.patch(f"{target}.issue_refund_note", side_effect=note),
        ):
            result = Command(stderr=io.StringIO()).sync_refunds(None)

        self.assertEqual(result, (1, 1))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, RazorpayRefund.Status.PENDING)
        self.assertFalse(Receipt.objects.filter(refund=first).exists())
        self.assertEqual(second.status, PROCESSED)
        self.assertTrue(Receipt.objects.filter(refund=second).exists())

    def test_the_sync_notes_a_processed_dashboard_refund(self) -> None:
        from server.management.commands.sync_razorpay_transactions import Command

        transaction = self.paid("d@example.com")
        entry = {
            "id": "rfnd_d",
            "status": "processed",
            "payment_id": transaction.payment_id,
            "amount": 75000,
        }
        with mock.patch(
            "server.management.commands.sync_razorpay_transactions.get_refunds",
            return_value=[entry],
        ):
            Command().sync_refunds(None)
        self.assertTrue(
            Receipt.objects.filter(kind=Receipt.Kind.REFUND, reference="rfnd_d").exists()
        )


def receipt_mails() -> list[dict[str, Any]]:
    return [
        task.data
        for task in Task.objects.filter(type=Task.TaskType.SEND_EMAIL)
        if task.data["subject"].startswith(("Receipt ", "Refund note "))
    ]


class TestReceiptEmail(ReceiptTestCase):
    def test_the_payer_gets_one_email_once_the_capture_commits(self) -> None:
        transaction = self.order(
            (make_player("e@example.com"), plan("regular", self.season), 75000)
        )
        with self.captureOnCommitCallbacks(execute=True):
            purchase.fulfil(transaction)
            purchase.fulfil(transaction)  # a rerun sends nothing more
        receipt = Receipt.objects.get(transaction=transaction)
        [mail] = receipt_mails()
        self.assertEqual(mail["to"], ["payer@example.com"])
        self.assertEqual(mail["subject"], f"Receipt {receipt.number} — India Ultimate")
        self.assertIn(receipt.number, mail["html_content"])
        self.assertIn("750.00", mail["html_content"])
        base = settings.EMAIL_INVITATION_BASE_URL
        self.assertTrue(base.startswith("http"), base)
        self.assertIn(f'href="{base}/receipts/{receipt.pk}"', mail["html_content"])
        self.assertIn(f'src="{base}/static/assets/logo-vertical.png"', mail["html_content"])

    def test_the_email_is_queued_only_after_the_commit(self) -> None:
        transaction = self.order(
            (make_player("c@example.com"), plan("regular", self.season), 75000)
        )
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            purchase.fulfil(transaction)
            self.assertEqual(receipt_mails(), [])  # the payment has not committed yet
        self.assertEqual(receipt_mails(), [])
        for callback in callbacks:
            callback()
        self.assertEqual(len(receipt_mails()), 1)

    def test_a_bug_in_the_email_never_undoes_the_payment(self) -> None:
        player = make_player("boom@example.com")
        transaction = self.order((player, plan("regular", self.season), 75000))
        with (
            mock.patch("server.receipts.emails.render_html", side_effect=RuntimeError("boom")),
            self.assertLogs("server.receipts.emails", level="ERROR") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            applied = purchase.fulfil(transaction)
        self.assertIn("could not be sent", logs.output[0])
        self.assertEqual(applied, 1)
        self.assertTrue(Subscription.objects.filter(player=player, is_active=True).exists())
        self.assertTrue(Receipt.objects.filter(transaction=transaction).exists())
        self.assertEqual(receipt_mails(), [])

    def test_a_bulk_resync_records_but_does_not_email(self) -> None:
        transaction = self.order(
            (make_player("q@example.com"), plan("regular", self.season), 75000)
        )
        with self.captureOnCommitCallbacks(execute=True):
            purchase.fulfil(transaction, notify=False)
        self.assertTrue(Receipt.objects.filter(transaction=transaction).exists())
        self.assertEqual(receipt_mails(), [])

    def test_no_email_for_a_payer_without_an_address(self) -> None:
        self.payer.user.email = ""
        self.payer.user.save()
        transaction = self.order(
            (make_player("n@example.com"), plan("regular", self.season), 75000)
        )
        with self.captureOnCommitCallbacks(execute=True):
            purchase.fulfil(transaction)
        self.assertTrue(Receipt.objects.filter(transaction=transaction).exists())
        self.assertEqual(receipt_mails(), [])

    def test_a_refund_note_is_emailed(self) -> None:
        transaction = self.order(
            (make_player("rn@example.com"), plan("regular", self.season), 75000)
        )
        purchase.fulfil(transaction, notify=False)
        refund = RazorpayRefund.objects.create(
            transaction=transaction, amount=75000, reason="x", status=PROCESSED
        )
        with self.captureOnCommitCallbacks(execute=True):
            note = issue_refund_note(refund)
        assert note is not None  # noqa: S101 - for mypy; the subject below checks the value
        [mail] = receipt_mails()
        self.assertEqual(mail["subject"], f"Refund note {note.number} — India Ultimate")

    def test_the_sync_with_no_email_records_a_refund_note_but_sends_none(self) -> None:
        transaction = self.order(
            (make_player("sn@example.com"), plan("regular", self.season), 75000)
        )
        purchase.fulfil(transaction, notify=False)
        entry = {
            "id": "rfnd_sn",
            "status": "processed",
            "payment_id": transaction.payment_id,
            "amount": 75000,
        }
        with (
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_transactions",
                return_value=[],
            ),
            mock.patch(
                "server.management.commands.sync_razorpay_transactions.get_refunds",
                return_value=[entry],
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            call_command("sync_razorpay_transactions", "--no-email")
        self.assertTrue(
            Receipt.objects.filter(kind=Receipt.Kind.REFUND, reference="rfnd_sn").exists()
        )
        self.assertEqual(receipt_mails(), [])
