"""What a person would pay for a tier, and whether they may."""

from dataclasses import dataclass

from server.core.models import Player
from server.membership.models import Membership, MembershipPlan
from server.membership.sponsorship import has_grant

NEW = "new"
UPGRADE = "upgrade"


class NotForSale(Exception):  # noqa: N818
    """This plan is not something this person can buy right now."""


class NeedsGrant(Exception):  # noqa: N818
    """This tier has to be approved before it can be bought."""


@dataclass(frozen=True)
class Quote:
    kind: str
    amount: int
    plan: MembershipPlan


def quote(player: Player, plan: MembershipPlan) -> Quote:
    """What this person would pay for this plan, or why they cannot have it.

    The amount always comes from the plan, never from the caller. A person
    buying their way up a tier pays only the difference.
    """
    if not plan.is_available:
        raise NotForSale(f"{plan.type.name} is not on sale for {plan.season.name}.")

    if plan.type.requires_grant and not has_grant(player, plan.season):
        raise NeedsGrant(f"{plan.type.name} has to be approved before it can be bought.")

    # An inactive row is left over from the old order-time creation, or is a
    # staff placeholder; a refunded one no longer counts. Both are bought over.
    held = (
        Membership.objects.for_season(plan.season)
        .filter(player=player, is_active=True)
        .select_related("plan__type")
        .first()
    )
    if held is None:
        return Quote(kind=NEW, amount=plan.amount, plan=plan)

    paid = held.amount_paid or 0
    # Checking the held tier's price as well as what was paid refuses a
    # downgrade from a tier staff gave away for less than its price.
    held_price = held.plan.amount if held.plan is not None else 0
    if plan.amount <= max(paid, held_price):
        current = held.plan.type.name if held.plan is not None else "a membership"
        raise NotForSale(
            f"This person already holds {current} for {plan.season.name}. "
            "Memberships can only move up a tier."
        )

    return Quote(kind=UPGRADE, amount=plan.amount - paid, plan=plan)
