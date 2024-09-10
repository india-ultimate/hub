from typing import Any

from django.core.management.base import BaseCommand

from server.transaction.client.phonepe import check_and_update_transaction
from server.transaction.models import PhonePeTransaction


class Command(BaseCommand):
    help = "Reconcile pending PhonePe Transactions"

    def handle(self, *args: Any, **options: Any) -> None:
        pending_transactions = PhonePeTransaction.objects.filter(
            status=PhonePeTransaction.TransactionStatusChoices.PENDING
        )
        n = pending_transactions.count()
        self.stdout.write(self.style.SUCCESS(f"Found {n} pending transactions in our DB..."))
        for transaction in pending_transactions:
            check_and_update_transaction(transaction)

        m = PhonePeTransaction.objects.filter(
            status=PhonePeTransaction.TransactionStatusChoices.PENDING
        ).count()

        self.stdout.write(self.style.SUCCESS(f"Updated status of {n - m} pending transactions."))
