import uuid
from typing import Any

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
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


@receiver(pre_save, sender=Membership)
def create_membership_number(sender: Any, instance: Membership, raw: bool, **kwargs: Any) -> None:
    if raw or instance.membership_number:
        return

    instance.membership_number = str(uuid.uuid4())[:8]
    return
