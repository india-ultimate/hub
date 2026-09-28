"""Handing out numbers, and freezing what a receipt says."""

import datetime

from django.db import transaction as db_transaction
from django.utils.timezone import now

from server.receipts.models import Receipt, ReceiptSequence
from server.receipts.money import financial_year, india_date
from server.receipts.rows import Row, group, legacy_row, person_label
from server.season.models import Season
from server.subscription.models import Subscription
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

RECEIPT_SERIES = "IU"
REFUND_SERIES = "RF"
SUBSCRIPTION = RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION


def next_number(series: str, when: datetime.datetime) -> tuple[str, str, int]:
    """The next number in a series for the financial year `when` falls in.

    Taken under a row lock inside the caller's transaction, so a rollback
    hands the number back and the series never skips. Outside a transaction
    the number would commit on its own and a later failure would burn it, so
    that is refused.
    """
    if not db_transaction.get_connection().in_atomic_block:
        raise RuntimeError("next_number must be called inside a transaction.atomic() block")
    year = financial_year(india_date(when))
    counter, _ = ReceiptSequence.objects.select_for_update().get_or_create(
        series=series, financial_year=year
    )
    counter.last += 1
    counter.save(update_fields=["last"])
    return f"{series}/{year}/{counter.last:05d}", year, counter.last


def _person(line: RazorpayTransactionPlayer) -> str:
    user = line.player.user
    return person_label(user.first_name, user.last_name, user.username, line.player.iu_id)


def _item(line: RazorpayTransactionPlayer) -> str:
    """What a line buys, read before the order is applied, so an upgrade
    still sees the tier it is moving up from."""
    assert line.plan is not None  # noqa: S101 - describe_items only passes lines with a plan
    tier = line.plan.type.name
    held = (
        Subscription.objects.filter(
            player_id=line.player_id,
            season=line.plan.season,
            is_active=True,
            refunded_at__isnull=True,
            plan__isnull=False,
        )
        .exclude(plan=line.plan)
        .select_related("plan__type")
        .first()
    )
    if held is not None and held.plan is not None and (line.amount or 0) < line.plan.amount:
        # "Upgrade from Regular to Patron Subscription": the word is said once.
        return f"Upgrade from {held.plan.type.name.removesuffix(' Subscription')} to {tier}"
    return tier


def _lines(transaction: RazorpayTransaction) -> list[RazorpayTransactionPlayer]:
    return list(
        RazorpayTransactionPlayer.objects.filter(transaction=transaction)
        .select_related("plan__type", "plan__season", "player__user")
        .order_by("id")
    )


def describe_items(transaction: RazorpayTransaction) -> dict[int, str]:
    """Line id -> what it buys, e.g. "Upgrade from Regular to Patron
    Subscription". Ask before the order is applied."""
    return {line.pk: _item(line) for line in _lines(transaction) if line.plan is not None}


def rows_for_order(
    transaction: RazorpayTransaction, items: dict[int, str] | None = None
) -> list[Row]:
    """The rows as the order reads now: people are labelled at this moment
    (so a new IU ID prints), the items from `items` or, if not given, now."""
    if items is None:
        items = describe_items(transaction)
    lines = _lines(transaction)
    if not lines or any(line.plan is None or line.amount is None for line in lines):
        season = transaction.season or Season.containing(india_date(transaction.payment_date))
        people = [_person(line) for line in lines]
        return [legacy_row(season.name if season else None, people, transaction.amount)]
    return group(
        [
            (
                f"{items[line.pk]}, {line.plan.season.name}",
                _person(line),
                line.amount or 0,
                line.pk,
            )
            for line in lines
            if line.plan is not None
        ]
    )


def issue_receipt(
    transaction: RazorpayTransaction,
    received_at: datetime.datetime | None = None,
    items: dict[int, str] | None = None,
) -> Receipt | None:
    """The receipt for a paid subscription order, issued once."""
    if transaction.type != SUBSCRIPTION:
        return None
    existing = Receipt.objects.filter(transaction=transaction, kind=Receipt.Kind.RECEIPT).first()
    if existing is not None:
        return existing
    when = received_at or now()
    rows = rows_for_order(transaction, items)
    number, year, sequence = next_number(RECEIPT_SERIES, when)
    user = transaction.user
    return Receipt.objects.create(
        kind=Receipt.Kind.RECEIPT,
        transaction=transaction,
        number=number,
        financial_year=year,
        sequence=sequence,
        issued_at=when,
        payer_name=f"{user.first_name} {user.last_name}".strip() or user.username,
        payer_email=user.email or "",
        payer_phone=user.phone or "",
        lines=rows,
        total=sum(row["amount"] for row in rows),
        reference=transaction.payment_id,
        order_id=transaction.order_id,
    )
