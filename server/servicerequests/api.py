from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Router

from server.core.models import Player, User
from server.season.models import Season
from server.subscription.models import SubscriptionPlan
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

    # Validate service player IDs if provided
    service_players = []
    if service_request_data.service_player_ids:
        try:
            service_players = list(
                Player.objects.filter(id__in=service_request_data.service_player_ids)
            )
            if len(service_players) != len(service_request_data.service_player_ids):
                return 400, {"message": "One or more player IDs are invalid"}
        except Exception:
            return 400, {"message": "Invalid player IDs provided"}

    # A sponsorship is for one season, which must offer a tier that needs a grant.
    season: Season | None = None
    if service_request_data.type == ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION:
        plan = (
            SubscriptionPlan.objects.filter(
                season__id=service_request_data.season_id or 0,
                is_available=True,
                type__requires_grant=True,
            )
            .select_related("season")
            .first()
        )
        if plan is None:
            return 400, {"message": "This season has no sponsored subscription to request"}
        season = plan.season

    # Create the service request
    service_request = ServiceRequest(
        user=request.user,
        type=service_request_data.type,
        message=service_request_data.message,
        season=season,
    )

    try:
        service_request.full_clean()
        service_request.save()

        # Add service players if provided
        if service_players:
            service_request.service_players.set(service_players)

        return 200, service_request
    except ValidationError as e:
        return 400, {"message": " ".join(e.messages)}
