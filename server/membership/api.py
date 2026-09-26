"""The membership and plan endpoints."""

from typing import Any

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router

from server.core.models import Guardianship, Player
from server.membership import catalog, pricing
from server.membership.models import Membership
from server.membership.schema import MembershipPlanSchema, MembershipSchema
from server.season.models import Season
from server.types import message_response

router = Router()


def may_see(user: Any, player: Player) -> bool:
    """The person themselves, their guardian, or staff."""
    return bool(
        user.is_staff
        or player.user_id == user.id
        or Guardianship.objects.filter(player=player, user_id=user.id).exists()
    )


@router.get(
    "/seasons/{season_id}/plans",
    response={200: list[MembershipPlanSchema], 403: message_response},
)
def season_plans(
    request: HttpRequest, season_id: int, player_id: int | None = None
) -> tuple[int, list[MembershipPlanSchema] | dict[str, str]]:
    """What a person can buy for a season, priced for them.

    Priced for a player, this says which tier they hold, so only they, their
    guardian or staff may ask.
    """
    season = get_object_or_404(Season, id=season_id)
    player = Player.objects.filter(id=player_id).first() if player_id else None
    if player is not None and not may_see(request.user, player):
        return 403, {"message": "You can only price a membership for yourself, or your ward"}

    offers = []
    for plan in catalog.plans_for(season):
        available, upgrade_from, upgrade_amount = True, None, None
        if player is not None:
            try:
                quote = pricing.quote(player, plan)
            except (pricing.NotForSale, pricing.NeedsGrant):
                available = False
            else:
                if quote.kind == pricing.UPGRADE:
                    upgrade_amount = quote.amount
                    held = (
                        Membership.objects.filter(player=player, season=season)
                        .live()
                        .select_related("plan__type")
                        .first()
                    )
                    upgrade_from = held.plan.type.name if held and held.plan is not None else None
        offers.append(
            MembershipPlanSchema(
                id=plan.id,
                slug=plan.type.slug,
                name=plan.type.name,
                description=plan.type.description,
                amount=plan.amount,
                requires_grant=plan.type.requires_grant,
                available_to_player=available,
                upgrade_from=upgrade_from,
                upgrade_amount=upgrade_amount,
            )
        )
    return 200, offers


@router.get("/players/{player_id}/memberships", response={200: list[MembershipSchema]})
def player_memberships(request: HttpRequest, player_id: int) -> list[Membership]:
    """Every season this person has been a member, newest first."""
    return list(
        Membership.objects.filter(player_id=player_id)
        .live()
        .select_related("season", "plan__type")
        .order_by("-season__start_date")
    )
