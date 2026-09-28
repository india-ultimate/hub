"""Turning a paid order into subscriptions."""

from django.db import IntegrityError
from django.db import transaction as db_transaction

from server.subscription.emails import queue_confirmation
from server.subscription.models import Subscription, SubscriptionPlan
from server.subscription.numbers import assign_number
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer


def fulfil(transaction: RazorpayTransaction, notify: bool = True) -> int:
    """Apply a captured payment. Returns how many lines it applied.

    Safe to run more than once: the callback, the webhook and the nightly
    sync all call it, and a line that already has a subscription is skipped.

    `notify` off skips the confirmation emails, for a bulk historical resync.
    """
    if transaction.status != RazorpayTransaction.TransactionStatusChoices.COMPLETED:
        return 0

    applied = 0
    with db_transaction.atomic():
        # Keep this: on production Postgres it serialises a webhook racing a
        # slow callback for the same order, which is a real race. It is a
        # no-op under SQLite tests, so nothing below depends on it either: a
        # line is only ever applied once because applying it sets
        # line.subscription, and the unique (player, season) on Subscription is
        # the backstop for two orders racing.
        RazorpayTransaction.objects.select_for_update().filter(pk=transaction.pk).first()
        lines = RazorpayTransactionPlayer.objects.select_related(
            "plan__season", "plan__type", "player__user"
        ).filter(
            transaction=transaction,
            plan__isnull=False,
            subscription__isnull=True,
            needs_review=False,
        )
        for line in lines:
            try:
                # A savepoint, so a clash on one line leaves the rest alone.
                with db_transaction.atomic():
                    if _apply(line, notify=notify):
                        applied += 1
            except IntegrityError:
                # Either another order created this season's subscription
                # between the read above and the insert, or assign_number ran
                # out of retries. Both land here, so the note names both.
                _flag(
                    line,
                    "This line could not be applied: either another payment created this "
                    "season's subscription at the same time, or no IU ID could "
                    "be allocated.",
                )
    return applied


def _flag(line: RazorpayTransactionPlayer, why: str) -> None:
    line.needs_review = True
    line.review_note = f"{why} Refund or apply by hand."
    line.save(update_fields=["needs_review", "review_note"])


def _apply(line: RazorpayTransactionPlayer, notify: bool = True) -> bool:
    plan = line.plan
    if plan is None:
        return False
    season = plan.season
    held = Subscription.objects.filter(player_id=line.player_id, season=season).first()
    amount = line.amount or 0

    if held is None:
        held = Subscription(
            player_id=line.player_id,
            season=season,
            start_date=season.start_date,
            end_date=season.end_date,
        )
        _activate(held, plan, amount)
    elif not held.is_active or held.refunded_at is not None:
        # An abandoned order left this behind, or a refund emptied it.
        _activate(held, plan, amount)
    elif (held.amount_paid or 0) + amount == plan.amount:
        # An upgrade: the same subscription moves up a tier.
        held.plan = plan
        held.amount_paid = (held.amount_paid or 0) + amount
        held.save(update_fields=["plan", "amount_paid"])
    else:
        _flag(
            line,
            f"Paid {amount} for {plan.type.name}, but this person already holds "
            f"a subscription for {season.name}.",
        )
        return False

    line.subscription = held
    line.save(update_fields=["subscription"])
    assign_number(held.player, season)
    if notify:
        queue_confirmation(held)
    return True


def _activate(subscription: Subscription, plan: SubscriptionPlan, amount: int) -> None:
    subscription.plan = plan
    subscription.amount_paid = amount
    subscription.start_date = plan.season.start_date
    subscription.end_date = plan.season.end_date
    subscription.is_active = True
    subscription.refunded_at = None
    subscription.save()
