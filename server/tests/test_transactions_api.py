from django.core.files.uploadedfile import SimpleUploadedFile

from server.tests.base import ApiBaseTestCase
from server.transaction.models import ManualTransaction, RazorpayTransaction


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
