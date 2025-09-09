from django.db import models
from django_prometheus.models import ExportModelOperationsMixin


class Season(ExportModelOperationsMixin("season"), models.Model):  # type: ignore[misc]
    start_date = models.DateField()
    end_date = models.DateField()
    name = models.CharField(max_length=255)
    annual_membership_amount = models.PositiveIntegerField(default=0)
    sponsored_annual_membership_amount = models.PositiveIntegerField(default=0)
    supporter_annual_membership_amount = models.PositiveIntegerField(default=0)
