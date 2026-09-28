"""Receipts for every subscription paid before receipts existed.

Numbered in the order the money came in, within each financial year, and
never emailed. Migration 0159 runs this once before the new release serves
traffic, so live payments carry on each year's series after these.

It is also the `issue_missing_receipts` command: an order the old release
captured after 0159 took its snapshot gets no receipt from the callback, the
webhook or the nightly sync, because all three see it as already settled.
Running this again picks those up. It is idempotent -- an order or refund
that already has one is skipped -- so a second run does nothing.

Everything here goes through `apps.get_model`, so the migration can hand it
the historical models and keep running against a fresh database. It calls
server.receipts.rows and server.receipts.money for the same reason those are
pinned there: their signatures must stay compatible with these calls.
"""

from typing import Any

from server.receipts.money import financial_year, india_date
from server.receipts.rows import group, legacy_row, person_label

SUBSCRIPTION = "annual-subscription"
PAID = ["completed", "refunded"]


def backfill(apps: Any, schema_editor: Any = None) -> tuple[int, int]:
    """Issue what is missing. Returns (receipts, refund notes) created."""
    Receipt = apps.get_model("server", "Receipt")  # noqa: N806
    Sequence = apps.get_model("server", "ReceiptSequence")  # noqa: N806
    Transaction = apps.get_model("server", "RazorpayTransaction")  # noqa: N806
    Line = apps.get_model("server", "RazorpayTransactionPlayer")  # noqa: N806
    Refund = apps.get_model("server", "RazorpayRefund")  # noqa: N806
    Season = apps.get_model("server", "Season")  # noqa: N806

    last = {(s.series, s.financial_year): s.last for s in Sequence.objects.all()}
    receipts = notes = 0

    def number(series: str, when: Any) -> tuple[str, str, int]:
        year = financial_year(india_date(when))
        last[(series, year)] = last.get((series, year), 0) + 1
        return f"{series}/{year}/{last[(series, year)]:05d}", year, last[(series, year)]

    def label(player: Any) -> str:
        user = player.user
        return person_label(user.first_name, user.last_name, user.username, player.iu_id)

    def season_name(order: Any) -> str | None:
        day = india_date(order.payment_date)
        season = order.season or (
            Season.objects.filter(start_date__lte=day, end_date__gte=day)
            .order_by("-start_date", "-id")
            .first()
        )
        return season.name if season else None

    done = Receipt.objects.filter(kind="receipt").values("transaction_id")
    orders = (
        Transaction.objects.filter(type=SUBSCRIPTION, status__in=PAID)
        .exclude(order_id__in=done)
        .select_related("user", "season")
        .order_by("payment_date", "order_id")
    )
    for order in orders.iterator():
        lines = list(
            Line.objects.filter(transaction=order)
            .select_related("player__user", "plan__type", "plan__season")
            .order_by("id")
        )
        if lines and all(line.plan_id and line.amount is not None for line in lines):
            rows = group(
                [
                    (
                        (
                            line.plan.type.name
                            if line.amount == line.plan.amount
                            else f"Upgrade to {line.plan.type.name}"
                        )
                        + f", {line.plan.season.name}",
                        label(line.player),
                        line.amount,
                        line.id,
                    )
                    for line in lines
                ]
            )
        else:
            rows = [
                legacy_row(season_name(order), [label(line.player) for line in lines], order.amount)
            ]
        text, year, sequence = number("IU", order.payment_date)
        user = order.user
        Receipt.objects.create(
            kind="receipt",
            transaction=order,
            number=text,
            financial_year=year,
            sequence=sequence,
            issued_at=order.payment_date,
            payer_name=f"{user.first_name} {user.last_name}".strip() or user.username,
            payer_email=user.email or "",
            payer_phone=user.phone or "",
            lines=rows,
            total=sum(row["amount"] for row in rows),
            reference=order.payment_id,
            order_id=order.order_id,
        )
        receipts += 1

    noted = Receipt.objects.filter(kind="refund").values("refund_id")
    refunds = (
        Refund.objects.filter(status="processed", transaction__type=SUBSCRIPTION)
        .exclude(pk__in=noted)
        .select_related("line__player__user")
        .order_by("created_at", "pk")
    )
    for refund in refunds.iterator():
        original = Receipt.objects.filter(
            transaction_id=refund.transaction_id, kind="receipt"
        ).first()
        if original is None:
            continue
        particulars, people = f"Refund against receipt {original.number}", []
        if refund.line_id:
            # Same rule as a live refund note: the line id first, and for a
            # legacy row (which has none) the person's label.
            live = label(refund.line.player)
            found = None
            for row in original.lines:
                if refund.line_id in row.get("line_ids", []):
                    found = (row, row["people"][row["line_ids"].index(refund.line_id)])
                    break
                if "line_ids" not in row:
                    person = next(
                        (p for p in row["people"] if live == p or live.startswith(f"{p} (")), None
                    )
                    if person is not None:
                        found = (row, person)
                        break
            if found is not None:
                row, person = found
                particulars, people = f"Refund: {row['particulars']}", [person]
        text, year, sequence = number("RF", refund.created_at)
        Receipt.objects.create(
            kind="refund",
            transaction_id=refund.transaction_id,
            refund=refund,
            original=original,
            number=text,
            financial_year=year,
            sequence=sequence,
            issued_at=refund.created_at,
            payer_name=original.payer_name,
            payer_email=original.payer_email,
            payer_phone=original.payer_phone,
            lines=[
                {
                    "particulars": particulars,
                    "people": people,
                    "quantity": 1,
                    "rate": refund.amount,
                    "amount": refund.amount,
                }
            ],
            total=refund.amount,
            reference=refund.razorpay_refund_id or "",
            order_id=original.order_id,
        )
        notes += 1

    for (series, year), value in last.items():
        Sequence.objects.update_or_create(
            series=series, financial_year=year, defaults={"last": value}
        )
    return receipts, notes


def unbackfill(apps: Any, schema_editor: Any = None) -> None:
    apps.get_model("server", "Receipt").objects.filter(kind="refund").delete()
    apps.get_model("server", "Receipt").objects.all().delete()
    apps.get_model("server", "ReceiptSequence").objects.all().delete()
