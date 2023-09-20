from pathlib import Path

from server.manual_transactions import validate_manual_transactions
from server.models import ManualTransaction
from server.tests.base import ApiBaseTestCase


class TestManualTransactions(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "bank-statement.csv"

        transactions = {
            "33680091811DC": 60000,
            "326013145864": 100,
        }
        for tid, amount in transactions.items():
            ManualTransaction.objects.create(transaction_id=tid, amount=amount, user=self.user)

    def test_validate_manual_transactions(self) -> None:
        self.assertEqual(2, ManualTransaction.objects.filter(validated=False).count())
        stats = validate_manual_transactions(self.fixture)
        self.assertEqual(4, stats["total"])
        self.assertEqual(2, stats["invalid_found"])
        self.assertEqual(1, stats["validated"])
        self.assertEqual(1, ManualTransaction.objects.filter(validated=False).count())
        self.assertFalse(ManualTransaction.objects.get(transaction_id="33680091811DC").validated)
