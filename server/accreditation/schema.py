from ninja import ModelSchema, Schema

from server.accreditation.models import Accreditation


class AccreditationSchema(ModelSchema):
    class Meta:
        model = Accreditation
        fields = "__all__"


class AccreditationFormSchema(Schema):
    player_id: int
