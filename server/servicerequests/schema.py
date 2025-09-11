from ninja import ModelSchema, Schema

from server.schema import PlayerMinSchema

from .models import ServiceRequest


class ServiceRequestSchema(ModelSchema):
    user_full_name: str
    service_players: list[PlayerMinSchema]

    @staticmethod
    def resolve_user_full_name(service_request: ServiceRequest) -> str:
        return service_request.user.get_full_name()

    @staticmethod
    def resolve_service_players(service_request: ServiceRequest) -> list[PlayerMinSchema]:
        return list(service_request.service_players.all())

    class Config:
        model = ServiceRequest
        model_fields = "__all__"


class ServiceRequestCreateSchema(Schema):
    type: str
    message: str
    service_player_ids: list[int] | None = None
