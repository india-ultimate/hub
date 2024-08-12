import uuid
from typing import Any

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, User
from server.season.models import Season
from server.tournament.models import Event


class Membership(ExportModelOperationsMixin("membership"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    membership_number = models.CharField(max_length=20, unique=True)
    is_annual = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    waiver_valid = models.BooleanField(default=False)
    waiver_signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    waiver_signed_at = models.DateTimeField(blank=True, null=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, blank=True, null=True)


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

    def __str__(self) -> str:
        return self.order_id

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "RazorpayTransaction":
        return create_transaction_from_order_data(cls, data)


@receiver(pre_save, sender=Membership)
def create_membership_number(sender: Any, instance: Membership, raw: bool, **kwargs: Any) -> None:
    if raw or instance.membership_number:
        return

    instance.membership_number = str(uuid.uuid4())[:8]
    return


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
