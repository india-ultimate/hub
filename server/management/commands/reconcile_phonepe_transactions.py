from typing import Any

from django.core.management.base import BaseCommand

from server.api import check_and_update_phonepe_transaction
from server.models import PhonePeTransaction


class Command(BaseCommand):
    help = "Reconcile pending PhonePe Transactions"

    def handle(self, *args: Any, **options: Any) -> None:
        pending_transactions = PhonePeTransaction.objects.filter(
            status=PhonePeTransaction.TransactionStatusChoices.PENDING
        )
        n = pending_transactions.count()
        for transaction in pending_transactions:
            check_and_update_phonepe_transaction(transaction)

        self.stdout.write(self.style.SUCCESS(f"Updated status of {n} pending transactions."))
