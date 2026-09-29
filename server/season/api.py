from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Router

from server.schema import Response

from .models import Season
from .schema import SeasonSchema

router = Router()


@router.get("/", auth=None, response={200: list[SeasonSchema]})
def list_seasons(request: HttpRequest) -> QuerySet[Season]:
    return Season.objects.all().order_by("-start_date")


# Must stay above any "/{season_id}" route.
@router.get("/current", auth=None, response={200: SeasonSchema, 404: Response})
def current_season(request: HttpRequest) -> tuple[int, Season | dict[str, str]]:
    """The season today falls inside, in IST. 404 when there is none."""
    season = Season.current()
    if season is None:
        return 404, {"message": "No season covers today"}
    return 200, season
