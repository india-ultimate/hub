from django.conf import settings

from server.core.models import User
from server.season.models import Season
from server.transaction.models import RazorpayTransaction


def pay_link(order_id: str) -> str:
    return f"{settings.PUBLIC_URL}/pay/{order_id}"


def receipt_link(receipt_id: int) -> str:
    return f"{settings.PUBLIC_URL}/receipts/{receipt_id}"


def unpaid_membership(user: User, player_id: int, season: Season | None = None) -> str | None:
    """The order_id of this user's membership order for the player that still waits to be paid."""
    order = (
        RazorpayTransaction.objects.filter(
            user=user,
            players=player_id,
            season=season or Season.current(),
            type=RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
        )
        .exclude(status__in=[*RazorpayTransaction.SETTLED, "failed"])
        .order_by("-payment_date")
        .first()
    )
    return order.order_id if order else None
