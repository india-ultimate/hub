"""Sending money back, and undoing what it paid for."""

from typing import Any

from django.db import transaction as db_transaction
from django.db.models import QuerySet, Sum
from django.utils.timezone import now

from server.core.models import User
from server.subscription.models import Subscription, SubscriptionPlan
from server.transaction.client.razorpay import CLIENT
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

# A refund in one of these states has taken the money back, or still may.
# Only a failed one leaves the payment whole.
STANDING = [
    RazorpayRefund.Status.REQUESTED,
    RazorpayRefund.Status.PENDING,
    RazorpayRefund.Status.PROCESSED,
]


class RefundRefused(Exception):  # noqa: N818 - it reads as a sentence where it is raised
    """This refund cannot be made, and no money has moved."""


def unrefunded(
    lines: QuerySet[RazorpayTransactionPlayer],
) -> QuerySet[RazorpayTransactionPlayer]:
    """The lines with no refund standing against them."""
    return lines.exclude(
        # line__isnull=False matters: a NOT IN list containing NULL matches
        # nothing at all, which would hide every line.
        pk__in=RazorpayRefund.objects.filter(status__in=STANDING, line__isnull=False).values("line")
    )


def refunded_total(transaction: RazorpayTransaction) -> int:
    """How much of this order has been given back."""
    total = RazorpayRefund.objects.filter(transaction=transaction, status__in=STANDING).aggregate(
        total=Sum("amount")
    )["total"]
    return int(total or 0)


def settle(transaction: RazorpayTransaction) -> None:
    """Say whether an order counts as refunded, by what stands against it.

    Refunded once the money back covers what was captured, which is also what
    stops the nightly sync marching it back to completed. Back to completed
    when a refund it was marked for turns out to have failed: the money never
    left, so the order is a payment again.
    """
    refunded = RazorpayTransaction.TransactionStatusChoices.REFUNDED
    covered = refunded_total(transaction) >= transaction.amount

    if covered and transaction.status != refunded:
        transaction.status = refunded
        transaction.save(update_fields=["status"])
    elif (
        not covered
        and transaction.status == refunded
        # Only an order the Hub itself marked refunded is taken back. One
        # marked by hand, with no refund on record, is left as staff set it.
        and RazorpayRefund.objects.filter(transaction=transaction).exists()
    ):
        transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
        transaction.save(update_fields=["status"])


def _send(
    transaction: RazorpayTransaction,
    line: RazorpayTransactionPlayer | None,
    amount: int,
    by: User | None,
    reason: str,
) -> RazorpayRefund:
    """Record the refund, then ask Razorpay for it. The caller holds the lock.

    Everything here runs inside the caller's transaction, so a crash before
    the gateway call just rolls back cleanly: nothing happened at Razorpay
    either, so there is nothing to recover. The window that matters is the
    other one: if anything after a successful call raises before the commit,
    this record rolls back while the money really has gone. That is
    deliberate, not an oversight — the nightly sync matches refunds only by
    `razorpay_refund_id`, never by the `hub_refund_id` note sent along with
    the request, so it finds this refund at Razorpay with no record here,
    records it as a dashboard-sourced one, and flags its line for review. Do
    not tidy the bookkeeping out of this block without keeping that recovery
    intact. A gateway refusal comes back as a `failed` record rather than an
    exception, so that record survives the caller's transaction; the caller
    raises once it has committed.
    """
    if refunded_total(transaction) + amount > transaction.amount:
        raise RefundRefused("That would refund more than was paid.")

    refund = RazorpayRefund.objects.create(
        transaction=transaction, line=line, amount=amount, reason=reason, created_by=by
    )
    try:
        answer: dict[str, Any] = CLIENT.payment.refund(
            transaction.payment_id,
            {"amount": amount, "notes": {"hub_refund_id": str(refund.pk)}},
        )
    except Exception as error:  # - the gateway's error is the message
        refund.status = RazorpayRefund.Status.FAILED
        refund.error = str(error)
        refund.save(update_fields=["status", "error"])
        return refund

    refund.razorpay_refund_id = answer.get("id")
    refund.status = (
        RazorpayRefund.Status.PROCESSED
        if answer.get("status") == "processed"
        else RazorpayRefund.Status.PENDING
    )
    refund.save(update_fields=["razorpay_refund_id", "status"])
    settle(transaction)
    return refund


def refund_line(line: RazorpayTransactionPlayer, by: User | None, reason: str) -> RazorpayRefund:
    """Send back what one person paid in one order, and undo what it bought."""
    if not reason.strip():
        raise RefundRefused("A refund needs a reason.")

    with db_transaction.atomic():
        # On production Postgres this serialises two staff clicking Refund at
        # once: the second waits here, then finds the line already refunded.
        RazorpayTransaction.objects.select_for_update().filter(pk=line.transaction_id).first()
        line.refresh_from_db()

        if RazorpayRefund.objects.filter(line=line, status__in=STANDING).exists():
            raise RefundRefused("This line has already been refunded.")

        amount = line.amount
        if not amount:
            raise RefundRefused(
                "This line has no amount of its own. Refund the whole order instead."
            )

        transaction = line.transaction
        subscription = line.subscription
        if subscription is not None:
            newer = unrefunded(
                RazorpayTransactionPlayer.objects.filter(subscription=subscription).exclude(
                    pk=line.pk
                )
            ).filter(transaction__payment_date__gt=transaction.payment_date)
            if newer.exists():
                raise RefundRefused(
                    "A later payment on this subscription has not been refunded. "
                    "Refund that first, or refund the subscription completely."
                )

        refund = _send(transaction, line, amount, by, reason)

        if refund.status == RazorpayRefund.Status.FAILED:
            pass  # No money moved, so nothing here changes either.
        elif subscription is not None:
            _undo(subscription, line)
        elif line.needs_review:
            # A line that was never applied. Refunding it settles the review.
            line.needs_review = False
            line.review_note = ""
            line.save(update_fields=["needs_review", "review_note"])

    if refund.status == RazorpayRefund.Status.FAILED:
        raise RefundRefused(f"Razorpay refused the refund: {refund.error}")
    return refund


def _undo(subscription: Subscription, line: RazorpayTransactionPlayer) -> None:
    """Put the subscription back as it was before this line paid for it.

    The line keeps pointing at the subscription, as the record of what it once
    bought; `purchase.fulfil` skips refunded lines by their refund.
    """
    earlier = (
        unrefunded(
            RazorpayTransactionPlayer.objects.filter(subscription=subscription).exclude(pk=line.pk)
        )
        .select_related("plan")
        .order_by("-transaction__payment_date")
        .first()
    )
    remaining = (subscription.amount_paid or 0) - (line.amount or 0)
    subscription.amount_paid = max(remaining, 0)

    if earlier is not None:
        subscription.plan = earlier.plan
    elif remaining <= 0:
        subscription.refunded_at = now()
        subscription.is_active = False
    else:
        # Money is still standing that no line here accounts for: a subscription
        # paid for before the Hub kept lines. It stays; the tier goes back to
        # the one that money buys this season, if exactly one does.
        tiers = SubscriptionPlan.objects.filter(season=subscription.season_id, amount=remaining)
        if len(tiers) == 1:
            subscription.plan = tiers[0]
        else:
            line.needs_review = True
            line.review_note = (
                f"Refunded, but {remaining / 100:.2f} paid earlier still stands and matches "
                "no single tier this season. The subscription keeps its tier; set it by hand."
            )
            line.save(update_fields=["needs_review", "review_note"])

    subscription.save(update_fields=["amount_paid", "refunded_at", "is_active", "plan"])


def mark_failed(refund: RazorpayRefund) -> None:
    """Razorpay says the money never went back. Take back what we did in hope.

    The Hub applies a refund as soon as Razorpay accepts it, which is right
    for the usual case, where it then processes. When one fails afterwards
    the subscription has to come back, the order stops counting as refunded,
    and the lines go to staff either way.
    """
    with db_transaction.atomic():
        refund.status = RazorpayRefund.Status.FAILED
        refund.save(update_fields=["status"])

        note = f"A refund the Hub made later failed at Razorpay. {_restore(refund)}"
        lines = RazorpayTransactionPlayer.objects.filter(transaction=refund.transaction)
        if refund.line_id is not None:
            lines = lines.filter(pk=refund.line_id)
        lines.update(needs_review=True, review_note=note)

        settle(refund.transaction)


def _restore(refund: RazorpayRefund) -> str:
    """Put back the subscription this failed refund had already taken apart."""
    line = refund.line
    subscription = line.subscription if line is not None else None
    if line is None or subscription is None or line.plan_id is None:
        # A registration, or a line that had nothing applied to undo. What
        # the payment bought was never touched, so there is nothing to put
        # back — but staff still have to decide what to do about the money.
        return "Check what this payment paid for."

    moved_on = (
        unrefunded(
            RazorpayTransactionPlayer.objects.filter(subscription=subscription).exclude(pk=line.pk)
        )
        .filter(transaction__payment_date__gt=refund.transaction.payment_date)
        .exists()
        or RazorpayRefund.objects.filter(line__subscription=subscription, status__in=STANDING)
        .exclude(pk=refund.pk)
        .exists()
    )
    if moved_on:
        return (
            "Another payment or refund has touched this subscription since, so it "
            "was left as it is. Put it right by hand."
        )

    subscription.amount_paid = int(subscription.amount_paid or 0) + int(line.amount or 0)
    subscription.plan = line.plan
    subscription.refunded_at = None
    subscription.is_active = True
    subscription.save(update_fields=["amount_paid", "plan", "refunded_at", "is_active"])
    return "The subscription it had emptied is back."


def refund_order(
    transaction: RazorpayTransaction, by: User | None, reason: str
) -> list[RazorpayRefund]:
    """Refund what is left of an order.

    A subscription order is refunded line by line. An order whose lines carry no
    amount of their own — a team, player or form registration — is refunded in
    one go for whatever has not been given back yet. What that paid for stays
    in place; staff undo it by hand.
    """
    if not reason.strip():
        raise RefundRefused("A refund needs a reason.")

    lines = unrefunded(RazorpayTransactionPlayer.objects.filter(transaction=transaction)).order_by(
        "-pk"
    )
    made = [refund_line(line, by, reason) for line in lines if line.amount]
    if made:
        return made

    with db_transaction.atomic():
        RazorpayTransaction.objects.select_for_update().filter(pk=transaction.pk).first()
        transaction.refresh_from_db()
        remaining = transaction.amount - refunded_total(transaction)
        if remaining <= 0:
            raise RefundRefused("This order has already been refunded.")
        refund = _send(transaction, None, remaining, by, reason)

    if refund.status == RazorpayRefund.Status.FAILED:
        raise RefundRefused(f"Razorpay refused the refund: {refund.error}")
    return [refund]


def refund_subscription(
    subscription: Subscription, by: User | None, reason: str
) -> list[RazorpayRefund]:
    """Give back everything paid for one subscription, newest payment first."""
    lines = unrefunded(
        RazorpayTransactionPlayer.objects.filter(subscription=subscription)
    ).order_by("-transaction__payment_date")
    return [refund_line(line, by, reason) for line in lines]
