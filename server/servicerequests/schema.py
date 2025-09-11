from ninja import ModelSchema, Schema

from .models import ServiceRequest


class ServiceRequestSchema(ModelSchema):
    user_full_name: str

    @staticmethod
    def resolve_user_full_name(service_request: ServiceRequest) -> str:
        return service_request.user.get_full_name()

    class Config:
        model = ServiceRequest
        model_fields = "__all__"


class ServiceRequestCreateSchema(Schema):
    type: str
    message: str
