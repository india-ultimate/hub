"""The catalog, what a person holds, and who may buy a discounted tier."""

import uuid
from typing import Any

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, User
from server.season.models import Season
from server.servicerequests.models import ServiceRequest  # noqa: F401
from server.tournament.models import Event


class Scope(models.TextChoices):
    PLAY_CHAMPIONSHIPS = "play_championships", "Play in series and championships"
    STAFF_CHAMPIONSHIPS = "staff_championships", "Coach or manage at series and championships"
    VOTE = "vote", "Vote in state and national elections"


# Before the catalog there was no Community tier, so every subscription was full.
LEGACY_SCOPES = frozenset(Scope)


class SubscriptionType(models.Model):
    """A tier. Stable across seasons; what it allows is its scopes."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    requires_grant = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]

    def __str__(self) -> str:
        return self.name

    def allows(self, scope: str) -> bool:
        # A forward query (rather than the `scopes` related manager) sidesteps
        # a django-stubs quirk: it can't yet see a reverse relation to a model
        # defined later in the same file.
        return SubscriptionTypeScope.objects.filter(type=self, scope=scope).exists()


class SubscriptionTypeScope(models.Model):
    """One thing a tier lets its holders do."""

    type = models.ForeignKey(SubscriptionType, related_name="scopes", on_delete=models.CASCADE)
    scope = models.CharField(max_length=40, choices=Scope.choices)

    class Meta:
        unique_together = ("type", "scope")

    def __str__(self) -> str:
        return f"{self.type.slug}:{self.scope}"


class SubscriptionPlan(models.Model):
    """A tier on sale in one season, at one price."""

    season = models.ForeignKey(Season, related_name="plans", on_delete=models.PROTECT)
    type = models.ForeignKey(SubscriptionType, related_name="plans", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField(help_text="In paise.")
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ("season", "type")
        ordering = ["season", "type__display_order"]

    def __str__(self) -> str:
        return f"{self.type.name} — {self.season.name}"


class Subscription(ExportModelOperationsMixin("subscription"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    subscription_number = models.CharField(max_length=20, unique=True)
    is_annual = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    waiver_valid = models.BooleanField(default=False)
    waiver_signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    waiver_signed_at = models.DateTimeField(blank=True, null=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, blank=True, null=True)


@receiver(pre_save, sender=Subscription)
def create_subscription_number(
    sender: Any, instance: Subscription, raw: bool, **kwargs: Any
) -> None:
    if raw or instance.subscription_number:
        return

    instance.subscription_number = str(uuid.uuid4())[:8]
    return
