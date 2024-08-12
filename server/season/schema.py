from ninja import ModelSchema

from .models import Season


class SeasonSchema(ModelSchema):
    class Config:
        model = Season
        model_fields = "__all__"
