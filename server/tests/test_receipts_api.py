import datetime

from django.test import TestCase

from server.core.models import User
from server.receipts.models import Receipt
from server.transaction.models import RazorpayTransaction

from .test_subscription_model import make_player

UTC = datetime.timezone.utc


def make_receipt(
    user: User, number: str, day: int, kind: str = "receipt", original: Receipt | None = None
) -> Receipt:
    transaction = (
        original.transaction
        if original
        else RazorpayTransaction.objects.create(
            order_id=f"order_{number}",
            payment_id=f"pay_{number}",
            amount=75000,
            currency="INR",
            user=user,
            status="completed",
        )
    )
    return Receipt.objects.create(
        kind=kind,
        transaction=transaction,
        original=original,
        number=number,
        financial_year="2026-27",
        sequence=day,
        issued_at=datetime.datetime(2026, 9, day, tzinfo=UTC),
        payer_name="Priya Rao",
        lines=[
            {
                "particulars": (
                    f"Refund against receipt {original.number}"
                    if original
                    else "Regular Subscription, Season 2026-2027"
                ),
                "people": ["A"],
                "quantity": 1,
                "rate": 75000,
                "amount": 75000,
            }
        ],
        total=75000,
        reference="pay",
        order_id=transaction.order_id,
    )


class TestReceiptsApi(TestCase):
    def setUp(self) -> None:
        self.owner = make_player("owner@example.com").user
        self.older = make_receipt(self.owner, "IU/2026-27/00001", 1)
        self.newer = make_receipt(self.owner, "IU/2026-27/00002", 5)
        self.note = make_receipt(
            self.owner, "RF/2026-27/00001", 9, kind="refund", original=self.older
        )
        make_receipt(make_player("other@example.com").user, "IU/2026-27/00003", 6)

    def test_the_list_holds_only_mine_newest_first_notes_after_their_receipt(self) -> None:
        self.client.force_login(self.owner)
        body = self.client.get("/api/receipts").json()
        self.assertEqual(
            [r["number"] for r in body],
            ["IU/2026-27/00002", "IU/2026-27/00001", "RF/2026-27/00001"],
        )
        expected = "Regular Subscription × 1 — Season 2026-2027"  # noqa: RUF001
        self.assertEqual(body[0]["summary"], expected)
        # A refund note says what it refunds as written, with no "x 1" appended.
        self.assertEqual(body[2]["summary"], "Refund against receipt IU/2026-27/00001")
        self.assertEqual(body[2]["original_id"], self.older.pk)

    def test_the_payer_and_staff_get_page_and_pdf(self) -> None:
        for user in (self.owner, User.objects.create(username="staff", email="s@x", is_staff=True)):
            self.client.force_login(user)
            page = self.client.get(f"/api/receipts/{self.older.pk}/page")
            self.assertEqual(page.status_code, 200)
            self.assertIn("IU/2026-27/00001", page.content.decode())
            # The Hub frames the page, and neither response may be cached.
            self.assertEqual(page["X-Frame-Options"], "SAMEORIGIN")
            self.assertEqual(page["Cache-Control"], "private, no-store")
            pdf = self.client.get(f"/api/receipts/{self.older.pk}/pdf")
            self.assertEqual(pdf.status_code, 200)
            self.assertEqual(pdf["Cache-Control"], "private, no-store")
            self.assertEqual(pdf["Content-Type"], "application/pdf")
            self.assertIn('filename="IU-2026-27-00001.pdf"', pdf["Content-Disposition"])

    def test_a_stranger_is_refused_page_and_pdf(self) -> None:
        self.client.force_login(make_player("nosy@example.com").user)
        for suffix in ("page", "pdf"):
            self.assertEqual(
                self.client.get(f"/api/receipts/{self.older.pk}/{suffix}").status_code, 403
            )
        self.assertEqual(self.client.get("/api/receipts").json(), [])

    def test_an_unknown_id_is_404(self) -> None:
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/receipts/999999/page").status_code, 404)

    def test_the_transactions_list_links_the_receipt(self) -> None:
        self.client.force_login(self.owner)
        rows = {r["order_id"]: r for r in self.client.get("/api/transactions/").json()}
        self.assertEqual(rows[self.older.order_id]["receipt_number"], "IU/2026-27/00001")
        self.assertEqual(rows[self.older.order_id]["receipt_id"], self.older.pk)
