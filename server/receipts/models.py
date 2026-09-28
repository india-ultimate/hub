"""A receipt or refund note, frozen as it was issued."""

from django.db import models

from server.transaction.models import RazorpayRefund, RazorpayTransaction


class ReceiptSequence(models.Model):
    """The last number handed out in one series and financial year."""

    series = models.CharField(max_length=4)
    financial_year = models.CharField(max_length=7)
    last = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("series", "financial_year")

    def __str__(self) -> str:
        return f"{self.series}/{self.financial_year}: {self.last}"


class Receipt(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        REFUND = "refund", "Refund note"

    kind = models.CharField(max_length=8, choices=Kind.choices)
    transaction = models.ForeignKey(
        RazorpayTransaction, related_name="receipts", on_delete=models.PROTECT
    )
    refund = models.OneToOneField(
        RazorpayRefund, related_name="note", on_delete=models.PROTECT, blank=True, null=True
    )
    original = models.ForeignKey(
        "self", related_name="refund_notes", on_delete=models.PROTECT, blank=True, null=True
    )
    number = models.CharField(max_length=16, unique=True)
    financial_year = models.CharField(max_length=7)
    sequence = models.PositiveIntegerField()
    issued_at = models.DateTimeField()
    payer_name = models.CharField(max_length=301)  # first + space + last, 150 each
    payer_email = models.CharField(max_length=254, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)
    lines = models.JSONField()
    total = models.PositiveIntegerField(help_text="In paise.")
    reference = models.CharField(
        max_length=255, blank=True, help_text="Razorpay payment or refund ID."
    )
    order_id = models.CharField(max_length=255)

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction"],
                condition=models.Q(kind="receipt"),
                name="one_receipt_per_order",
            )
        ]

    def __str__(self) -> str:
        return self.number
