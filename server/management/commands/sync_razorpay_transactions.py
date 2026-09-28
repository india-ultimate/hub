import itertools
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.transaction.client.razorpay import get_transactions, mark_transaction_completed
from server.transaction.models import RazorpayTransaction
from server.transaction.utils import apply_transaction

STATUSES = {s.value: s for s in RazorpayTransaction.TransactionStatusChoices}


class Command(BaseCommand):
    help = (
        "Import Razorpay transactions from the last week. Pass --no-email for a bulk "
        "historical resync, so people who paid long ago are not mailed a confirmation "
        "for a subscription they already have."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--no-email",
            action="store_true",
            help="Apply the payments but queue no confirmation emails.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        notify = not options["no_email"]
        transactions = get_transactions()
        transactions_by_status = itertools.groupby(transactions, key=lambda x: x["status"])

        for status_, ts in transactions_by_status:
            status_value = "completed" if status_ == "captured" else status_
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
                    # A payment Razorpay captured but whose callback never
                    # reached us still has to hand over what it bought.
                    apply_transaction(transaction, notify=notify)
            else:
                # NOTE: Not sure if we need to do any additional actions for
                # other statuses like refunded, for instance. May be we deal
                # with it manually for now. If the transactions are being
                # processed oldest first, may be we can set the subscriptions to
                # inactive based on this status?
                n = qs.update(status=status)

            self.stdout.write(
                self.style.SUCCESS(f"Updated status of {n} transactions to {status_value}.")
            )
