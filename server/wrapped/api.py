from django.http import HttpRequest
from ninja import Router

from server.core.models import Player, User
from server.schema import Response
from server.types import message_response

from .models import PlayerWrapped
from .schema import PlayerWrappedSchema

router = Router()

# Year validation constants
MIN_YEAR = 2000
MAX_YEAR = 2100


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@router.get(
    "/",
    response={200: list[PlayerWrappedSchema], 400: Response, 404: Response},
)
def get_my_wrapped_data(
    request: AuthenticatedHttpRequest,
) -> tuple[int, list[PlayerWrapped] | message_response]:
    """
    Get all wrapped data for the logged-in user.
    Returns all years of wrapped data for the authenticated user's player profile.
    """
    try:
        player = request.user.player_profile
    except Player.DoesNotExist:
        return 404, {"message": "Player profile not found"}

    wrapped_data = PlayerWrapped.objects.filter(player=player).order_by("-year")
    return 200, list(wrapped_data)


@router.get(
    "/{year}",
    response={200: PlayerWrappedSchema, 400: Response, 404: Response},
)
def get_my_wrapped_data_by_year(
    request: AuthenticatedHttpRequest, year: int
) -> tuple[int, PlayerWrapped | message_response]:
    """
    Get wrapped data for a specific year for the logged-in user.
    """
    if year < MIN_YEAR or year > MAX_YEAR:
        return 400, {"message": "Invalid year"}

    try:
        player = request.user.player_profile
    except Player.DoesNotExist:
        return 404, {"message": "Player profile not found"}

    try:
        wrapped_data = PlayerWrapped.objects.get(player=player, year=year)
    except PlayerWrapped.DoesNotExist:
        return 404, {"message": f"Wrapped data for year {year} not found"}

    return 200, wrapped_data
