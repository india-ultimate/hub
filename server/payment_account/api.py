"""What a state association sees of the payments made into its own Razorpay account."""

import csv
from typing import Any, cast

from django.db.models import Max, Q, QuerySet, Sum
from django.db.models.functions import Coalesce
from django.http import Http404, HttpRequest, HttpResponse
from ninja import Router

from server.core.models import User
from server.payment_account.models import PaymentAccount, viewable_by
from server.receipts.money import india_date
from server.tournament.models import Event
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

router = Router()

PAGE_SIZE = 50
Status = RazorpayTransaction.TransactionStatusChoices
Kind = RazorpayTransaction.TransactionTypeChoices
# Only money that moved. Abandoned checkouts are noise to a state, and its
# own Razorpay dashboard has them.
SHOWN = [Status.COMPLETED, Status.REFUNDED]
STATUSES = {"paid": [Status.COMPLETED], "refunded": [Status.REFUNDED], "all": SHOWN}
TEAM_KINDS = [Kind.TEAM_REGISTRATION, Kind.PARTIAL_TEAM_REGISTRATION]
# A full fee and the rest after a partial one are both TEAM_REGISTRATION.
LABELS: dict[str, str] = {
    Kind.TEAM_REGISTRATION: "Team fee",
    Kind.PARTIAL_TEAM_REGISTRATION: "Partial team fee",
    Kind.PLAYER_REGISTRATION: "Player fees",
}
CSV_HEADER = [
    "Date",
    "Tournament",
    "Team",
    "For",
    "Paid by",
    "Payer email",
    "Players",
    "Base fee (INR)",
    "Late penalty (INR)",
    "Days late",
    "Amount (INR)",
    "Refunded (INR)",
    "Status",
    "Payment ID",
    "Order ID",
]


def _number(notes: dict[str, Any], key: str) -> int | None:
    """A number from the order's notes; None for an order placed before they were kept."""
    return int(notes[key]) if key in notes else None


def _rupees(paise: int | None) -> str:
    return "" if paise is None else f"{paise / 100:.2f}"


def _account(request: HttpRequest, slug: str) -> PaymentAccount:
    # Not found rather than forbidden: an outsider can't tell which accounts exist.
    account = viewable_by(cast(User, request.user)).filter(slug=slug).first()
    if account is None:
        raise Http404
    return account


def _events(account: PaymentAccount) -> list[Event]:
    """Events with payments into this account, the most recently paid first."""
    return list(
        Event.objects.filter(
            razorpaytransaction__account=account, razorpaytransaction__status__in=SHOWN
        )
        .annotate(last_paid=Max("razorpaytransaction__payment_date"))
        .order_by("-last_paid")
    )


def _event_id(events: list[Event], asked: int | None) -> int | None:
    if asked is not None:
        return asked
    return events[0].id if events else None


def _in_event(account: PaymentAccount, event_id: int | None) -> QuerySet[RazorpayTransaction]:
    rows = RazorpayTransaction.objects.filter(account=account, status__in=SHOWN)
    return rows.filter(event_id=event_id) if event_id is not None else rows.none()


def _filtered(
    account: PaymentAccount, event_id: int | None, status: str, q: str
) -> QuerySet[RazorpayTransaction]:
    rows = _in_event(account, event_id).filter(status__in=STATUSES.get(status, STATUSES["paid"]))
    if q:
        rows = rows.filter(
            Q(team__name__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(payment_id__icontains=q)
            | Q(order_id__icontains=q)
        )
    return (
        rows.select_related("event", "team", "user")
        .prefetch_related("players__user")
        .annotate(
            refunded=Coalesce(
                Sum("refunds__amount", filter=Q(refunds__status=RazorpayRefund.Status.PROCESSED)),
                0,
            )
        )
        .order_by("-payment_date", "-order_id")
    )


def _totals(account: PaymentAccount, event_id: int | None) -> dict[str, int]:
    """The tournament's totals, whatever the status filter or search."""
    rows = _in_event(account, event_id)
    collected = rows.aggregate(total=Coalesce(Sum("amount"), 0))["total"]
    refunded = RazorpayRefund.objects.filter(
        transaction__in=rows, status=RazorpayRefund.Status.PROCESSED
    ).aggregate(total=Coalesce(Sum("amount"), 0))["total"]
    paid = rows.filter(status=Status.COMPLETED)
    return {
        "collected": collected,
        "refunded": refunded,
        "net": collected - refunded,
        "teams_paid": paid.filter(type__in=TEAM_KINDS).values("team").distinct().count(),
        "players_paid": RazorpayTransactionPlayer.objects.filter(
            transaction__in=paid.filter(type=Kind.PLAYER_REGISTRATION)
        )
        .values("player")
        .distinct()
        .count(),
    }


def _row(t: RazorpayTransaction) -> dict[str, Any]:
    return {
        "order_id": t.order_id,
        "payment_id": t.payment_id,
        "date": india_date(t.payment_date).isoformat(),
        "event": t.event.title if t.event else "",
        "team": t.team.name if t.team else "",
        "type": t.type,
        "for": LABELS.get(t.type, t.get_type_display()),
        "payer": {"name": t.user.get_full_name(), "email": t.user.email},
        "players": sorted(p.user.get_full_name() for p in t.players.all()),
        "base_amount": _number(t.notes, "base_amount"),
        "penalty_amount": _number(t.notes, "penalty_amount"),
        "days_late": _number(t.notes, "days_late"),
        "amount": t.amount,
        "refunded": t.refunded,
        "status": t.status,
    }


def _summary(account: PaymentAccount) -> dict[str, Any]:
    return {"slug": account.slug, "name": account.name, "is_test_mode": account.is_test_mode}


@router.get("/", response={200: list[dict[str, Any]]})
def list_accounts(request: HttpRequest) -> list[dict[str, Any]]:
    return [_summary(a) for a in viewable_by(cast(User, request.user))]


@router.get("/{slug}/transactions", response={200: dict[str, Any]})
def transactions(
    request: HttpRequest,
    slug: str,
    event: int | None = None,
    status: str = "paid",
    q: str = "",
    page: int = 1,
) -> dict[str, Any]:
    account = _account(request, slug)
    events = _events(account)
    event_id = _event_id(events, event)
    rows = _filtered(account, event_id, status, q.strip())
    start = (max(1, page) - 1) * PAGE_SIZE
    return {
        "account": _summary(account),
        "event": event_id,
        "events": [{"id": e.id, "title": e.title} for e in events],
        "totals": _totals(account, event_id),
        "count": rows.count(),
        "page_size": PAGE_SIZE,
        "results": [_row(t) for t in rows[start : start + PAGE_SIZE]],
    }


def _safe(text: str) -> str:
    """Stop a spreadsheet reading user-typed text as a formula."""
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/{slug}/transactions.csv")
def transactions_csv(
    request: HttpRequest, slug: str, event: int | None = None, status: str = "paid", q: str = ""
) -> HttpResponse:
    account = _account(request, slug)
    event_id = _event_id(_events(account), event)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{account.slug}-payments.csv"'
    writer = csv.writer(response)
    writer.writerow(CSV_HEADER)
    for t in _filtered(account, event_id, status, q.strip()):
        row = _row(t)
        writer.writerow(
            [
                row["date"],
                _safe(row["event"]),
                _safe(row["team"]),
                row["for"],
                _safe(row["payer"]["name"]),
                _safe(row["payer"]["email"]),
                _safe("; ".join(row["players"])),
                _rupees(row["base_amount"]),
                _rupees(row["penalty_amount"]),
                "" if row["days_late"] is None else row["days_late"],
                _rupees(row["amount"]),
                _rupees(row["refunded"]),
                row["status"],
                row["payment_id"],
                row["order_id"],
            ]
        )
    return response
