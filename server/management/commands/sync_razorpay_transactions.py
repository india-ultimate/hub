import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.timezone import get_current_timezone

from server.subscription.refunds import mark_failed, settle
from server.transaction.client.razorpay import (
    get_refunds,
    get_transactions,
    mark_transaction_completed,
)
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)
from server.transaction.utils import apply_transaction

STATUSES = {s.value: s for s in RazorpayTransaction.TransactionStatusChoices}

# Razorpay's refund statuses, as the Hub records them.
REFUND_STATUSES = {
    "processed": RazorpayRefund.Status.PROCESSED,
    "failed": RazorpayRefund.Status.FAILED,
    "pending": RazorpayRefund.Status.PENDING,
}


class Command(BaseCommand):
    help = (
        "Import Razorpay transactions and refunds from the last week. Pass --no-email "
        "for a bulk historical resync, so people who paid long ago are not mailed a "
        "confirmation for a subscription they already have."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--no-email",
            action="store_true",
            help="Apply the payments but queue no confirmation emails.",
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="Look back to this date (YYYY-MM-DD) instead of one week.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        notify = not options["no_email"]
        since = None
        if options["since"] is not None:
            try:
                day = datetime.date.fromisoformat(options["since"])
            except ValueError as error:
                raise CommandError("--since wants a date as YYYY-MM-DD.") from error
            since = datetime.datetime.combine(day, datetime.time.min, tzinfo=get_current_timezone())

        order_ids_by_status: dict[str, set[str]] = {}
        for payment in get_transactions(since):
            status_value = "completed" if payment["status"] == "captured" else payment["status"]
            order_ids_by_status.setdefault(status_value, set()).add(payment["order_id"])
        # A card that failed before a retry was captured leaves both payments
        # on one order. Any capture means the order is paid, so the failed try
        # must not mark it failed again every night.
        paid = order_ids_by_status.get("completed", set())

        for status_value, order_ids in order_ids_by_status.items():
            status = STATUSES[status_value]
            qs = (
                RazorpayTransaction.objects.filter(order_id__in=order_ids).exclude(status=status)
                # A refund is the last word on an order: nothing Razorpay
                # reports about its payments moves it again.
                .exclude(status=RazorpayTransaction.TransactionStatusChoices.REFUNDED)
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
                n = qs.exclude(order_id__in=paid).update(status=status)

            self.stdout.write(
                self.style.SUCCESS(f"Updated status of {n} transactions to {status_value}.")
            )

        recorded = self.sync_refunds(since)
        self.stdout.write(self.style.SUCCESS(f"Recorded {recorded} refunds."))

    def sync_refunds(self, since: datetime.datetime | None) -> int:
        """Bring the Hub's record of refunds in line with Razorpay's."""
        recorded = 0
        for entry in get_refunds(since):
            status = REFUND_STATUSES.get(entry["status"], RazorpayRefund.Status.PENDING)
            existing = RazorpayRefund.objects.filter(razorpay_refund_id=entry["id"]).first()

            if existing is not None:
                if existing.status == status:
                    continue
                recorded += 1
                if status == RazorpayRefund.Status.FAILED:
                    # The Hub gave back what this refund bought as soon as
                    # Razorpay accepted it. None of that happened after all.
                    mark_failed(existing)
                else:
                    existing.status = status
                    existing.save(update_fields=["status"])
                    settle(existing.transaction)
                continue

            if status == RazorpayRefund.Status.FAILED:
                continue

            # Made in the Razorpay dashboard. Record it and let staff decide;
            # the Hub never changes a subscription for a refund it did not start.
            transaction = RazorpayTransaction.objects.filter(payment_id=entry["payment_id"]).first()
            if transaction is None:
                continue
            RazorpayRefund.objects.create(
                transaction=transaction,
                amount=entry["amount"],
                razorpay_refund_id=entry["id"],
                status=status,
                source=RazorpayRefund.Source.RAZORPAY_DASHBOARD,
                reason="Refunded in the Razorpay dashboard",
            )
            recorded += 1
            RazorpayTransactionPlayer.objects.filter(transaction=transaction).update(
                needs_review=True,
                review_note="Refunded in the Razorpay dashboard. Check what it paid for.",
            )
            # This is what finally marks the two refunded team registrations
            # the audit found, which Razorpay still reports as captured.
            settle(transaction)

        return recorded
