import datetime

from django.conf import settings
from django.db.models import Q
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from ninja import Router, Schema
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken

from server.core.models import User
from server.mcp.redirects import redirect_allowed
from server.schema import Response
from server.types import message_response

router = Router()

SCOPE_WORDS = {
    "hub:read": "See your Hub data",
    "hub:write": "Make changes in Hub as you",
}


class AuthenticatedHttpRequest(HttpRequest):
    user: User


class ConnectedAppSchema(Schema):
    application_id: int
    name: str
    connected_at: datetime.datetime
    scopes: list[str]


def _is_mcp_client(application: Application) -> bool:
    uris = application.redirect_uris.split()
    return bool(uris) and all(redirect_allowed(uri) for uri in uris)


def _require_enabled() -> None:
    if not settings.MCP_ENABLED:
        raise Http404


@router.get("/me/connected-apps", response={200: list[ConnectedAppSchema]})
def list_connected_apps(request: AuthenticatedHttpRequest) -> list[dict[str, object]]:
    _require_enabled()
    live = Q(expires__gt=now())
    access = AccessToken.objects.filter(user=request.user)
    refresh = RefreshToken.objects.filter(user=request.user, revoked__isnull=True)
    apps = []
    for application in Application.objects.filter(
        Q(accesstoken__in=access.filter(live)) | Q(refreshtoken__in=refresh)
    ).distinct():
        if not _is_mcp_client(application):
            continue
        tokens = access.filter(application=application)
        created = [*tokens.values_list("created", flat=True)]
        created += refresh.filter(application=application).values_list("created", flat=True)
        scopes = {s for t in tokens for s in t.scope.split()}
        apps.append(
            {
                "application_id": application.pk,
                "name": application.name,
                "connected_at": min(created),
                "scopes": [words for scope, words in SCOPE_WORDS.items() if scope in scopes],
            }
        )
    return apps


@router.delete("/me/connected-apps/{application_id}", response={200: Response, 404: Response})
def disconnect_app(request: AuthenticatedHttpRequest, application_id: int) -> message_response:
    _require_enabled()
    application = get_object_or_404(
        Application.objects.filter(
            Q(accesstoken__user=request.user) | Q(refreshtoken__user=request.user)
        ).distinct(),
        pk=application_id,
    )
    if not _is_mcp_client(application):
        raise Http404
    # Refresh tokens reference access tokens, so they go first
    RefreshToken.objects.filter(user=request.user, application=application).delete()
    AccessToken.objects.filter(user=request.user, application=application).delete()
    Grant.objects.filter(user=request.user, application=application).delete()
    return {"message": f"Disconnected {application.name}"}
