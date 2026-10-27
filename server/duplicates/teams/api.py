"""Team admins merging their own duplicate teams, or asking staff to."""

from typing import Any

from django.db import transaction
from django.http import HttpRequest
from ninja import Router

from server.core.models import Team, User
from server.duplicates.relations import MergeIncompleteError
from server.duplicates.teams.merge import (
    TeamMergeBlockedError,
    blockers,
    compare,
    default_keeper,
    label,
    logo_of,
    merge_teams,
)
from server.duplicates.teams.schema import (
    MergeTeamsSchema,
    OutcomeSchema,
    PreviewSchema,
    TeamIdsSchema,
)
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.types import message_response

router = Router()

# More copies of one team than production has ever held.
MAX_TEAMS = 10
MAX_MESSAGE = 2000


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _pick(
    request: AuthenticatedHttpRequest, team_ids: list[int]
) -> tuple[list[Team], set[int]] | tuple[int, message_response]:
    """The teams, and which of them the person admins; or why not."""
    ids = set(team_ids)
    if len(ids) < 2:  # noqa: PLR2004
        return 400, {"message": "Pick at least two teams"}
    if len(ids) > MAX_TEAMS:
        return 400, {"message": f"Merge at most {MAX_TEAMS} teams at a time"}
    teams = list(Team.objects.filter(pk__in=ids).order_by("pk"))
    if len(teams) != len(ids):
        return 404, {"message": "One of these teams no longer exists"}
    admin_of = set(request.user.admin_teams.filter(pk__in=ids).values_list("pk", flat=True))
    if not admin_of:
        return 403, {"message": "You can only merge a team you are an admin of"}
    return teams, admin_of


def _pending(teams: list[Team]) -> bool:
    return ServiceRequest.objects.filter(
        type=ServiceRequestType.REQUEST_TEAM_MERGE,
        status=ServiceRequestStatus.PENDING,
        service_teams__in=teams,
    ).exists()


@router.post(
    "/preview",
    response={
        200: PreviewSchema,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def preview(request: AuthenticatedHttpRequest, body: TeamIdsSchema) -> Any:
    picked = _pick(request, body.team_ids)
    if isinstance(picked[0], int):
        return picked
    teams, admin_of = picked
    return 200, {
        "teams": [
            {
                "id": team.pk,
                "name": team.name,
                "slug": team.slug,
                "logo": logo_of(team),
                "label": label(team),
            }
            for team in teams
        ],
        "lines": [
            {"label": line.label, "values": line.values, "differs": line.differs}
            for line in compare(teams)
        ],
        "blockers": blockers(teams),
        "keeper_id": default_keeper(teams).pk,
        "can_merge": len(admin_of) == len(teams),
        "admin_of": sorted(admin_of),
        "pending": _pending(teams),
    }


@router.post(
    "/",
    response={
        200: OutcomeSchema,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def merge(request: AuthenticatedHttpRequest, body: MergeTeamsSchema) -> Any:
    picked = _pick(request, body.team_ids)
    if isinstance(picked[0], int):
        return picked
    teams, admin_of = picked
    can_merge = len(admin_of) == len(teams)
    keeper = next((team for team in teams if team.pk == body.keeper_id), None)
    if keeper is None:
        return 400, {"message": "Pick the team to keep"}
    others = [team for team in teams if team != keeper]
    logo = next((team for team in teams if team.pk == body.logo_id), None)

    if can_merge:
        try:
            merge_teams(keeper, others, actor=request.user, logo=logo)
        except TeamMergeBlockedError as blocked:
            return 400, {"message": "; ".join(blocked.args[0])}
        except MergeIncompleteError:
            return 400, {"message": "These teams could not be merged. Please contact us."}
        return 200, {"merged": True, "slug": keeper.slug}

    found = blockers(teams)
    if found:
        return 400, {"message": "; ".join(found)}
    message = body.message.strip()
    if not message:
        return 400, {"message": "Tell us why these are the same team"}
    if len(message) > MAX_MESSAGE:
        return 400, {"message": f"Keep it under {MAX_MESSAGE} characters"}
    if _pending(teams):
        return 400, {"message": "A merge request for these teams is already waiting for review"}
    with transaction.atomic():
        service_request = ServiceRequest.objects.create(
            user=request.user,
            type=ServiceRequestType.REQUEST_TEAM_MERGE,
            message=message,
            keep_team=keeper,
            logo_team=logo,
        )
        service_request.service_teams.set(teams)
    return 200, {"merged": False, "request_id": service_request.pk}
