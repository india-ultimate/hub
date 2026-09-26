"""The membership and plan endpoints."""

from typing import Any

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router

from server.core.models import Guardianship, Player
from server.membership import catalog, pricing
from server.membership.models import Membership, SponsorshipGrant
from server.membership.schema import MembershipPlanSchema, MembershipSchema
from server.season.models import Season
from server.types import message_response

router = Router()

# One group payment's worth. Enough for any real team, too few to list every
# person on financial support in one request.
MAX_GRANT_LOOKUP = 50


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


@router.get("/seasons/{season_id}/grants", response={200: list[int], 400: message_response})
def season_grants(
    request: HttpRequest, season_id: int, player_ids: str = ""
) -> tuple[int, list[int] | dict[str, str]]:
    """Which of these players may buy a grant-only tier this season.

    One query for the whole group, so the group-payment page never has to ask
    per person, and never has to guess from the legacy `Player.sponsored`
    column, which says nothing about this season.
    """
    wanted = [int(part) for part in player_ids.split(",") if part.strip().isdigit()]
    if len(wanted) > MAX_GRANT_LOOKUP:
        return 400, {"message": f"Ask about at most {MAX_GRANT_LOOKUP} players at a time"}
    if not wanted:
        return 200, []
    return 200, list(
        SponsorshipGrant.objects.filter(season_id=season_id, player_id__in=wanted).values_list(
            "player_id", flat=True
        )
    )


@router.get(
    "/players/{player_id}/memberships",
    response={200: list[MembershipSchema], 403: message_response},
)
def player_memberships(
    request: HttpRequest, player_id: int
) -> tuple[int, list[Membership] | dict[str, str]]:
    """Every season this person has been a member, newest first.

    Only for the person, their guardian, or staff: it carries what they paid,
    refunds, and the name of whoever signed their waiver.
    """
    player = get_object_or_404(Player, id=player_id)
    if not may_see(request.user, player):
        return 403, {"message": "You can only see your own memberships, or your ward's"}
    return 200, list(
        Membership.objects.filter(player_id=player_id)
        .live()
        .select_related("season", "plan__type")
        .order_by("-season__start_date")
    )
