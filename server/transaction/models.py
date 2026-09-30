import enum
from typing import Any

from django.db import models
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, Team, User
from server.payment_account.models import PaymentAccount
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


class RazorpayTransactionPlayer(models.Model):
    """One person in one order. For subscription orders, what they're buying."""

    # The table was auto-created for the many-to-many with a bigint key
    # (DEFAULT_AUTO_FIELD was already BigAutoField), verified against the
    # production schema. Declared so state matches, and no ALTER is generated.
    id = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(
        "server.RazorpayTransaction",
        on_delete=models.CASCADE,
        db_column="razorpaytransaction_id",
    )
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    plan = models.ForeignKey(
        "server.SubscriptionPlan", on_delete=models.PROTECT, blank=True, null=True
    )
    amount = models.PositiveIntegerField(blank=True, null=True, help_text="In paise.")
    subscription = models.ForeignKey(
        "server.Subscription", on_delete=models.SET_NULL, blank=True, null=True
    )
    needs_review = models.BooleanField(default=False)
    review_note = models.TextField(blank=True)

    class Meta:
        db_table = "server_razorpaytransaction_players"
        unique_together = ("transaction", "player")

    def __str__(self) -> str:
        return f"{self.transaction_id} — {self.player}"


class RazorpayTransaction(ExportModelOperationsMixin("razorpay_transaction"), models.Model):  # type: ignore[misc]
    class TransactionStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    # An unpaid order is stored with Razorpay's own order status, "created",
    # not PENDING: the order data is saved as Razorpay returns it. So "still
    # open" means "not settled", never "== PENDING".
    SETTLED = ("completed", "refunded")

    class TransactionTypeChoices(models.TextChoices):
        ANNUAL_SUBSCRIPTION = "annual-subscription", _("Annual Subscription")
        TEAM_REGISTRATION = "team-reg", _("Team Registration")
        PARTIAL_TEAM_REGISTRATION = "partial-team-reg", _("Partial Team Registration")
        PLAYER_REGISTRATION = "player-reg", _("Player Registration")
        FORM_PAYMENT = "form-payment", _("Form Payment")

    order_id = models.CharField(primary_key=True, max_length=255)
    payment_id = models.CharField(max_length=255)
    payment_signature = models.CharField(max_length=255)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    # FIXME: payment_date is actually order_date, currently
    payment_date = models.DateTimeField(auto_now_add=True)
    # NOTE: These dates are for the subscription for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the subscription on payment success.
    start_date = models.DateField(default="1900-01-01")
    end_date = models.DateField(default="1900-01-01")
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player, through=RazorpayTransactionPlayer)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    type = models.CharField(
        max_length=30,
        choices=TransactionTypeChoices.choices,
        default=TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
    )
    # The account the order was placed on, fixed when it is created: every
    # later call about it (verify, webhook, sync, refund) goes to this one,
    # even if the event is pointed elsewhere afterwards. None is ours.
    account = models.ForeignKey(
        PaymentAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        blank=True,
        null=True,
    )
    # The notes sent to Razorpay with the order, saved as sent: for a
    # registration, base_amount, penalty_amount and days_late (strings, in
    # paise). Empty for orders placed before this field existed.
    notes = models.JSONField(default=dict, blank=True)

    class Meta:
        permissions = [("refund_razorpaytransaction", "Can refund payments")]

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
    # NOTE: These dates are for the subscription for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the subscription on payment success.
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


class RazorpayRefund(models.Model):
    """Money sent back through Razorpay, for one person's line or a whole order."""

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Requested")
        PENDING = "pending", _("Pending")
        PROCESSED = "processed", _("Processed")
        FAILED = "failed", _("Failed")

    class Source(models.TextChoices):
        HUB = "hub", _("Hub")
        RAZORPAY_DASHBOARD = "razorpay_dashboard", _("Razorpay dashboard")

    transaction = models.ForeignKey(
        RazorpayTransaction, related_name="refunds", on_delete=models.PROTECT
    )
    # No line for a refund of a whole order: a team or form registration has
    # no per-person amount to give back.
    line = models.ForeignKey(
        RazorpayTransactionPlayer,
        related_name="refunds",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    amount = models.PositiveIntegerField(help_text="In paise.")
    razorpay_refund_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.HUB)
    reason = models.TextField()
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.amount} on {self.transaction_id}"
