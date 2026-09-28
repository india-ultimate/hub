"""Which tiers are on sale in a season, and at what price."""

from django.db.models import QuerySet

from server.season.models import Season
from server.subscription.models import SubscriptionPlan

PATRON = "patron"
REGULAR = "regular"
DISCOUNTED = "discounted"
COMMUNITY = "community"


def plans_for(season: Season, available_only: bool = True) -> QuerySet[SubscriptionPlan]:
    """The plans a person could be shown for a season, cheapest concern first."""
    plans = SubscriptionPlan.objects.filter(season=season).select_related("type")
    if available_only:
        plans = plans.filter(is_available=True)
    return plans.order_by("type__display_order")


def plan_for(season: Season, slug: str) -> SubscriptionPlan | None:
    """One season's plan for a tier, or None if that tier isn't offered."""
    return (
        SubscriptionPlan.objects.filter(season=season, type__slug=slug)
        .select_related("type")
        .first()
    )


def copy_plans(source: Season, target: Season) -> int:
    """Give a new season the previous season's tiers and prices.

    Staff then edit the amounts. Plans the target already has are left alone,
    so running this twice changes nothing.
    """
    existing = set(SubscriptionPlan.objects.filter(season=target).values_list("type", flat=True))
    created = [
        SubscriptionPlan(
            season=target, type=plan.type, amount=plan.amount, is_available=plan.is_available
        )
        for plan in SubscriptionPlan.objects.filter(season=source)
        if plan.type.pk not in existing
    ]
    SubscriptionPlan.objects.bulk_create(created)
    return len(created)
