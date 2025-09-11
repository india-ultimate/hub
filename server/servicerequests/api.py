from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Router

from server.core.models import User
from server.types import message_response

from .models import ServiceRequest, ServiceRequestType
from .schema import ServiceRequestCreateSchema, ServiceRequestSchema

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@router.get("/", response={200: list[ServiceRequestSchema]})
def get_user_service_requests(request: AuthenticatedHttpRequest) -> QuerySet[ServiceRequest]:
    """Get all service requests for the authenticated user"""
    return ServiceRequest.objects.filter(user=request.user).order_by("-created_at")


@router.post("/", response={200: ServiceRequestSchema, 400: message_response})
def create_service_request(
    request: AuthenticatedHttpRequest, service_request_data: ServiceRequestCreateSchema
) -> tuple[int, ServiceRequest | dict[str, str]]:
    """Create a new service request"""
    # Validate the request type
    if service_request_data.type not in [choice[0] for choice in ServiceRequestType.choices]:
        return 400, {"message": "Invalid service request type"}

    # Create the service request
    service_request = ServiceRequest(
        user=request.user, type=service_request_data.type, message=service_request_data.message
    )

    try:
        service_request.full_clean()
        service_request.save()
        return 200, service_request
    except ValidationError as e:
        return 400, {"message": " ".join(e.messages)}
