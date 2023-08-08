import itertools
from typing import Any

from django.core.management.base import BaseCommand
from server.api import mark_transaction_completed
from server.models import RazorpayTransaction
from server.utils import get_transactions

STATUSES = {s.value: s for s in RazorpayTransaction.TransactionStatusChoices}


class Command(BaseCommand):
    help = "Import Razorpay transactions from the last week"

    def handle(self, *args: Any, **options: Any) -> None:
        transactions = get_transactions()
        transactions_by_status = itertools.groupby(transactions, key=lambda x: x["status"])

        for status_value, ts in transactions_by_status:
            if status_value == "captured":
                status_value = "completed"
            status = STATUSES[status_value]
            order_ids = {t["order_id"] for t in ts}
            qs = (
                RazorpayTransaction.objects.filter(order_id__in=order_ids).exclude(status=status)
                # .order_by("payment_date") NOTE: This is actually order
                # date. We could sort transactions based on transactions data,
                # though, if required
            )

            if status == RazorpayTransaction.TransactionStatusChoices.COMPLETED:
                n = qs.count()
                for transaction in qs:
                    mark_transaction_completed(transaction)
            else:
                # NOTE: Not sure if we need to do any additional actions for
                # other statuses like refunded, for instance. May be we deal
                # with it manually for now. If the transactions are being
                # processed oldest first, may be we can set the memberships to
                # inactive based on this status?
                n = qs.update(status=status)

            self.stdout.write(
                self.style.SUCCESS(f"Updated status of {n} transactions to {status_value}.")
            )
