from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Router

from .models import Season
from .schema import SeasonSchema

router = Router()


@router.get("/", auth=None, response={200: list[SeasonSchema]})
def list_seasons(request: HttpRequest) -> QuerySet[Season]:
    return Season.objects.all().order_by("start_date")
