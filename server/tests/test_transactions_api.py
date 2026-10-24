import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext

from server.core.models import Player, User
from server.series.models import SeriesRegistration
from server.tests.base import ApiBaseTestCase
from server.tests.test_eligibility import make_series
from server.transaction.models import ManualTransaction, PhonePeTransaction, RazorpayTransaction


class TestTransactionsApi(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def test_only_invalid_lists_unvalidated_manual_transactions(self) -> None:
        ManualTransaction.objects.create(transaction_id="A1", amount=100, user=self.user)
        ManualTransaction.objects.create(
            transaction_id="B2", amount=100, user=self.user, validated=True
        )

        # The Validate Transactions page asks with only_manual too, but a caller
        # that leaves it off used to get a 500: only manual ones have `validated`.
        response = self.client.get("/api/transactions/?user_only=false&only_invalid=true")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["A1"], [t["transaction_id"] for t in response.json()])

    def test_only_invalid_leaves_out_gateways_that_cannot_be_validated(self) -> None:
        self.assertFalse(RazorpayTransaction.objects.exists())
        response = self.client.get("/api/transactions/?user_only=false&only_invalid=true")
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_a_statement_without_the_expected_columns_is_refused(self) -> None:
        response = self.client.post(
            "/api/transactions/bulk-validate",
            {"bank_statement": SimpleUploadedFile("s.csv", b"Date,Amount\n1,2\n")},
        )

        self.assertEqual(400, response.status_code, response.content)
        message = response.json()["message"]
        self.assertIn("Chq/Ref Number", message)
        self.assertIn("Credit Amount", message)

    def test_listing_every_transaction_takes_the_same_queries_however_many(self) -> None:
        series = make_series(self.season)
        series.teams.set(self.teams[:3])
        self.event.series = series
        self.event.save()
        n = iter(range(100))

        def pay() -> None:
            i = next(n)
            user = User.objects.create(username=f"payer{i}@example.com", first_name="P")
            player = Player.objects.create(user=user, date_of_birth="1990-01-01")
            SeriesRegistration.objects.create(series=series, team=self.teams[0], player=player)
            for model, extra in (
                (ManualTransaction, {"transaction_id": f"M{i}"}),
                (RazorpayTransaction, {"order_id": f"o{i}", "status": "completed"}),
                (PhonePeTransaction, {"transaction_id": uuid.uuid4(), "status": "completed"}),
            ):
                paid = model.objects.create(amount=100, user=user, event=self.event, **extra)
                paid.players.add(player)

        pay()
        url = "/api/transactions/?user_only=false"
        with CaptureQueriesContext(connection) as before:
            self.assertEqual(200, self.client.get(url).status_code)
        for _ in range(3):
            pay()
        with CaptureQueriesContext(connection) as after:
            rows = self.client.get(url).json()

        self.assertEqual(12, len(rows))
        self.assertEqual(len(before), len(after))
