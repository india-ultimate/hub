"""The catalog, what a person holds, and who may buy a discounted tier."""

from django.db import models
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


class SubscriptionQuerySet(models.QuerySet["Subscription"]):
    def live(self) -> "SubscriptionQuerySet":
        """Everything a refund has not taken back."""
        return self.filter(refunded_at__isnull=True)

    def for_season(self, season: Season | None) -> "SubscriptionQuerySet":
        if season is None:
            return self.none()
        return self.live().filter(season=season)

    def current(self) -> "SubscriptionQuerySet":
        return self.for_season(Season.current())

    def for_event(self, event: Event) -> "SubscriptionQuerySet":
        return self.for_season(Season.containing(event.start_date))

    def with_scope(self, scope: str, season: Season | None) -> "SubscriptionQuerySet":
        """Members of a season whose tier allows something.

        A subscription with no tier predates the catalog, when every subscription
        was a full one, so it allows everything.
        """
        return self.for_season(season).filter(
            models.Q(plan__isnull=True) | models.Q(plan__type__scopes__scope=scope)
        )


class Subscription(ExportModelOperationsMixin("subscription"), models.Model):  # type: ignore[misc]
    """What one player holds for one season."""

    player = models.ForeignKey(Player, related_name="subscriptions", on_delete=models.CASCADE)
    season = models.ForeignKey(Season, related_name="subscriptions", on_delete=models.PROTECT)
    # Kept only so the release still running during a deploy can read these
    # columns. Nothing writes or reads them any more: the number lives on
    # Player, and every subscription now belongs to a season. Field and column
    # are removed together in the follow-up branch.
    subscription_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    is_annual = models.BooleanField(blank=True, null=True)
    plan = models.ForeignKey(
        SubscriptionPlan,
        related_name="subscriptions",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
    )
    amount_paid = models.PositiveIntegerField(blank=True, null=True, help_text="In paise.")
    refunded_at = models.DateTimeField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    waiver_valid = models.BooleanField(default=False)
    waiver_signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    waiver_signed_at = models.DateTimeField(blank=True, null=True)

    objects = SubscriptionQuerySet.as_manager()

    class Meta:
        # unique_together, not UniqueConstraint: the merge engine's
        # _breaks_uniqueness and _conflicting_row read only unique_together,
        # and with a constraint a merge of two accounts holding the same
        # season would raise IntegrityError and roll the whole merge back.
        unique_together = ("player", "season")

    def __str__(self) -> str:
        return f"{self.player} — {self.season}"

    @property
    def tier(self) -> str | None:
        return self.plan.type.slug if self.plan is not None else None

    def allows(self, scope: str) -> bool:
        if self.plan is None:
            return scope in LEGACY_SCOPES
        return self.plan.type.allows(scope)
