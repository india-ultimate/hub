from django.db import models
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import User
from server.transaction.models import RazorpayTransaction


class FieldType(models.TextChoices):
    TEXT = "text", _("Short text")
    TEXTAREA = "textarea", _("Long text")
    NUMBER = "number", _("Number")
    EMAIL = "email", _("Email")
    DROPDOWN = "dropdown", _("Dropdown")
    CHECKBOX = "checkbox", _("Checkboxes (multi-select)")
    RADIO = "radio", _("Single choice")
    DATE = "date", _("Date")


# Field types that need a list of options to choose from.
CHOICE_FIELD_TYPES = {FieldType.DROPDOWN, FieldType.CHECKBOX, FieldType.RADIO}


class Form(ExportModelOperationsMixin("form"), models.Model):  # type: ignore[misc]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    # List of field definitions, each:
    # {"key": str, "label": str, "type": FieldType, "required": bool, "options": [str]}
    fields = models.JSONField(default=list)
    # Amount in paise. Null/blank means the form is free.
    payment_amount = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title

    @property
    def needs_payment(self) -> bool:
        return self.payment_amount is not None and self.payment_amount > 0


class FormResponse(ExportModelOperationsMixin("form_response"), models.Model):  # type: ignore[misc]
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # Answers keyed by field key.
    answers = models.JSONField(default=dict)
    is_paid = models.BooleanField(default=False)
    transaction = models.ForeignKey(
        RazorpayTransaction, on_delete=models.SET_NULL, blank=True, null=True
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.form.title} - {self.user.get_full_name()}"
