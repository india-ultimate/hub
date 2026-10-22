import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player
from server.utils import today


def not_in_the_future(date: datetime.date) -> None:
    # A day's grace: it is already tomorrow east of India.
    if date > today() + datetime.timedelta(days=1):
        raise ValidationError("The date of issue can't be in the future.")


class Accreditation(ExportModelOperationsMixin("accreditation"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    is_valid = models.BooleanField(default=False)

    class AccreditationLevel(models.TextChoices):
        STANDARD = "STD", _("Standard")
        ADVANCED = "ADV", _("Advanced")

    level = models.CharField(max_length=10, choices=AccreditationLevel.choices)
    date = models.DateField(validators=[not_in_the_future])
    # Set from the certificate; without one, 18 months after the date.
    expiry_date = models.DateField(null=True, blank=True)
    certificate = models.FileField(upload_to="accreditation_certificates/", max_length=256)
    wfdf_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    # From a WFDF Academy certificate; rules.wfdf.sport ones have none.
    certificate_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^[0-9]{10}[A-Z0-9]{2}$")],
        error_messages={"unique": "This Certificate Code is already on another player's profile."},
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()  # Also turns a date given as a string into a date
        if self.expiry_date is None:
            self.expiry_date = self.date + relativedelta(months=18)
        self.is_valid = self.expiry_date >= today()
        super().save(*args, **kwargs)
