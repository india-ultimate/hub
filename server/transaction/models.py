import enum
from typing import Any

from django.db import models
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, Team, User
from server.season.models import Season
from server.tournament.models import Event


class AuthenticatedHttpRequest(HttpRequest):
    user: User


class PaymentGateway(enum.Enum):
    RAZORPAY = "R"
    PHONEPE = "P"
    MANUAL = "M"


def create_transaction_from_order_data(cls: Any, data: dict[str, Any]) -> Any:
    fields = {f.name for f in cls._meta.fields}
    attrs_data = {key: value for key, value in data.items() if key in fields}
    transaction = cls.objects.create(**attrs_data)
    players = data.get("players", [])
    for player in players:
        transaction.players.add(player)
    return transaction


class RazorpayTransaction(ExportModelOperationsMixin("razorpay_transaction"), models.Model):  # type: ignore[misc]
    class TransactionStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    class TransactionTypeChoices(models.TextChoices):
        ANNUAL_MEMBERSHIP = "annual-membership", _("Annual Membership")
        TEAM_REGISTRATION = "team-reg", _("Team Registration")
        PLAYER_REGISTRATION = "player-reg", _("Player Registration")

    order_id = models.CharField(primary_key=True, max_length=255)
    payment_id = models.CharField(max_length=255)
    payment_signature = models.CharField(max_length=255)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    # FIXME: payment_date is actually order_date, currently
    payment_date = models.DateTimeField(auto_now_add=True)
    # NOTE: These dates are for the membership for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the membership on payment success.
    start_date = models.DateField(default="1900-01-01")
    end_date = models.DateField(default="1900-01-01")
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    type = models.CharField(
        max_length=30,
        choices=TransactionTypeChoices.choices,
        default=TransactionTypeChoices.ANNUAL_MEMBERSHIP,
    )

    def __str__(self) -> str:
        return self.order_id

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "RazorpayTransaction":
        return create_transaction_from_order_data(cls, data)


class PhonePeTransaction(ExportModelOperationsMixin("phonepe_transaction"), models.Model):  # type: ignore[misc]
    class TransactionStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        ERROR = "error", _("Error")
        DECLINED = "declined", _("Declined")

    transaction_id = models.UUIDField(primary_key=True)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    transaction_date = models.DateTimeField(auto_now_add=True)
    # NOTE: These dates are for the membership for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the membership on payment success.
    start_date = models.DateField(default="1900-01-01")
    end_date = models.DateField(default="1900-01-01")
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.transaction_id)

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "PhonePeTransaction":
        return create_transaction_from_order_data(cls, data)


class ManualTransaction(ExportModelOperationsMixin("manual_transaction"), models.Model):  # type: ignore[misc]
    transaction_id = models.CharField(primary_key=True, max_length=255)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    payment_date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)
    validated = models.BooleanField(default=False)
    validation_comment = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.transaction_id

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "ManualTransaction":
        return create_transaction_from_order_data(cls, data)
