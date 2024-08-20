from django.db.models import QuerySet
from ninja import ModelSchema

from server.series.models import Series
from server.series.schema import SeriesMinSchema

from .models import Season


class SeasonSchema(ModelSchema):
    series: list[SeriesMinSchema]

    @staticmethod
    def resolve_series(season: Season) -> QuerySet[Series]:
        return season.series.all()

    class Config:
        model = Season
        model_fields = "__all__"
