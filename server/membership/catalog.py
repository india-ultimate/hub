"""Which tiers are on sale in a season, and at what price."""

from django.db.models import QuerySet

from server.core.models import Player
from server.membership.models import Membership, MembershipPlan
from server.season.models import Season

PATRON = "patron"
REGULAR = "regular"
DISCOUNTED = "discounted"
COMMUNITY = "community"


def plans_for(season: Season, available_only: bool = True) -> QuerySet[MembershipPlan]:
    """The plans a person could be shown for a season, cheapest concern first."""
    plans = MembershipPlan.objects.filter(season=season).select_related("type")
    if available_only:
        plans = plans.filter(is_available=True)
    return plans.order_by("type__display_order")


def season_to_buy(player: Player) -> Season | None:
    """The season this person would buy a membership for next.

    This season, unless they already hold it, in which case the next one.
    None when there is no season to buy at all.
    """
    current = Season.current()
    if current is None:
        return None
    if not Membership.objects.for_season(current).filter(player=player, is_active=True).exists():
        return current
    return Season.objects.filter(start_date__gt=current.start_date).order_by("start_date").first()


def plan_for(season: Season, slug: str) -> MembershipPlan | None:
    """One season's plan for a tier, or None if that tier isn't offered."""
    return (
        MembershipPlan.objects.filter(season=season, type__slug=slug).select_related("type").first()
    )


def copy_plans(source: Season, target: Season) -> int:
    """Give a new season the previous season's tiers and prices.

    Staff then edit the amounts. Plans the target already has are left alone,
    so running this twice changes nothing.
    """
    existing = set(MembershipPlan.objects.filter(season=target).values_list("type", flat=True))
    created = [
        MembershipPlan(
            season=target, type=plan.type, amount=plan.amount, is_available=plan.is_available
        )
        for plan in MembershipPlan.objects.filter(season=source)
        if plan.type.pk not in existing
    ]
    MembershipPlan.objects.bulk_create(created)
    return len(created)
