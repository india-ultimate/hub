import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction as db_transaction
from django.utils.timezone import get_current_timezone

from server.receipts.issue import issue_refund_note
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

# Razorpay payment statuses that mean "not captured yet", mapped onto the
# Hub's own PENDING -- neither is a status the Hub records directly.
UNPAID_STATUSES = {"created", "authorized"}

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
            help="Apply payments and refunds but queue no confirmation, receipt or refund-note emails.",
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
            razorpay_status = payment["status"]
            if razorpay_status == "captured":
                status_value = "completed"
            elif razorpay_status in UNPAID_STATUSES:
                status_value = "pending"
            else:
                status_value = razorpay_status
            order_ids_by_status.setdefault(status_value, set()).add(payment["order_id"])
        # A card that failed before a retry was captured leaves both payments
        # on one order. Any capture means the order is paid, so the failed try
        # must not mark it failed again every night.
        paid = order_ids_by_status.get("completed", set())

        for status_value, order_ids in order_ids_by_status.items():
            status = STATUSES.get(status_value)
            if status is None:
                self.stderr.write(
                    self.style.WARNING(
                        f"Unknown Razorpay status {status_value!r} for {len(order_ids)} "
                        "order(s); skipping them."
                    )
                )
                continue
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

        recorded, failed = self.sync_refunds(since, notify=notify)
        self.stdout.write(self.style.SUCCESS(f"Recorded {recorded} refunds."))
        if failed:
            self.stderr.write(
                self.style.ERROR(
                    f"{failed} refund(s) could not be synced; the next run retries them."
                )
            )

    def sync_refunds(self, since: datetime.datetime | None, notify: bool = True) -> tuple[int, int]:
        """Bring the Hub's record of refunds in line with Razorpay's.

        Returns (recorded, failed). One bad entry must not stop the rest:
        its own transaction has rolled back, so the next sync sees it as it
        was and tries again.
        """
        recorded = failed = 0
        for entry in get_refunds(since):
            try:
                recorded += self._sync_refund(entry, notify)
            except Exception as error:  # reported here, retried by the next sync
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"Refund {entry['id']} was not synced: {error!r}")
                )
        return recorded, failed

    def _sync_refund(self, entry: dict[str, Any], notify: bool) -> int:
        """Sync one Razorpay refund entry; 1 if it changed the Hub's record."""
        status = REFUND_STATUSES.get(entry["status"], RazorpayRefund.Status.PENDING)
        existing = RazorpayRefund.objects.filter(razorpay_refund_id=entry["id"]).first()

        if existing is not None:
            if existing.status == status:
                return 0
            # The status change, what follows from it and the note stand or
            # fall together: were the note to fail, the next sync must still
            # see the old status and try again.
            with db_transaction.atomic():
                # Take the order's row first, as refunds.refund_line does:
                # issue_refund_note locks the receipt sequence, so a sync that
                # locked the order second would deadlock against a staff refund.
                RazorpayTransaction.objects.select_for_update().filter(
                    pk=existing.transaction_id
                ).first()
                if status == RazorpayRefund.Status.FAILED:
                    # The Hub gave back what this refund bought as soon as
                    # Razorpay accepted it. None of that happened after all.
                    mark_failed(existing)
                else:
                    existing.status = status
                    existing.save(update_fields=["status"])
                    issue_refund_note(existing, notify=notify)
                    settle(existing.transaction)
            return 1

        if status == RazorpayRefund.Status.FAILED:
            return 0

        # Made in the Razorpay dashboard. Record it and let staff decide;
        # the Hub never changes a subscription for a refund it did not start.
        transaction = RazorpayTransaction.objects.filter(payment_id=entry["payment_id"]).first()
        if transaction is None:
            return 0
        with db_transaction.atomic():
            # The order's row first here too, so this sync and a staff refund
            # always take the order and the receipt sequence in the same order.
            RazorpayTransaction.objects.select_for_update().filter(pk=transaction.pk).first()
            refund = RazorpayRefund.objects.create(
                transaction=transaction,
                amount=entry["amount"],
                razorpay_refund_id=entry["id"],
                status=status,
                source=RazorpayRefund.Source.RAZORPAY_DASHBOARD,
                reason="Refunded in the Razorpay dashboard",
            )
            RazorpayTransactionPlayer.objects.filter(transaction=transaction).update(
                needs_review=True,
                review_note="Refunded in the Razorpay dashboard. Check what it paid for.",
            )
            # This is what finally marks the two refunded team registrations
            # the audit found, which Razorpay still reports as captured.
            settle(transaction)
            issue_refund_note(refund, notify=notify)
        return 1
