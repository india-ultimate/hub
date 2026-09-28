import datetime
from unittest import mock

from django.db import transaction as db_transaction
from django.test import TestCase

from server.core.models import Player
from server.receipts import rows
from server.receipts.issue import issue_receipt, next_number
from server.receipts.models import Receipt, ReceiptSequence
from server.season.models import Season
from server.subscription import purchase
from server.subscription.models import SubscriptionPlan
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

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
