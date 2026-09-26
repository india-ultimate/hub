"""Granting and revoking the discounted tier."""

from server.core.models import Player, User
from server.membership.models import SponsorshipGrant
from server.season.models import Season
from server.servicerequests.models import ServiceRequest


def grant(
    player: Player,
    season: Season,
    by: User | None = None,
    request: ServiceRequest | None = None,
    note: str = "",
) -> SponsorshipGrant:
    """Entitle a player to the discounted tier for one season.

    Granting the same season twice is a no-op, so an admin re-saving an
    approved request cannot double up.
    """
    entitlement, _ = SponsorshipGrant.objects.get_or_create(
        player=player,
        season=season,
        defaults={"granted_by": by, "request": request, "note": note},
    )
    return entitlement


def has_grant(player: Player, season: Season | None) -> bool:
    if season is None:
        return False
    return SponsorshipGrant.objects.filter(player=player, season=season).exists()
