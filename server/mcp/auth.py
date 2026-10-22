from dataclasses import dataclass

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from oauth2_provider.oauth2_backends import get_oauthlib_core

from server.core.models import User

SCOPES = ("hub:read", "hub:write")
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"


@dataclass(frozen=True)
class TokenInfo:
    user: User
    scopes: frozenset[str]
    client_id: str


def resource_matches(request_uri: str, audiences: list[str]) -> bool:
    return settings.MCP_RESOURCE_URL in audiences


def has_bearer(request: HttpRequest) -> bool:
    return request.headers.get("Authorization", "").lower().startswith("bearer ")


def authenticate(request: HttpRequest) -> TokenInfo | None:
    if not has_bearer(request):
        return None
    valid, oauth_request = get_oauthlib_core().verify_request(request, scopes=[])
    if not valid:
        return None
    token = oauth_request.access_token
    if (
        token.user is None
        or not token.user.is_active
        or settings.MCP_RESOURCE_URL not in token.resource
    ):
        return None
    return TokenInfo(token.user, frozenset(token.scope.split()), token.application.client_id)


def _challenge(response: HttpResponse, *params: str) -> HttpResponse:
    metadata = f'resource_metadata="{settings.PUBLIC_URL}{METADATA_PATH}"'
    scope = f'scope="{" ".join(SCOPES)}"'
    response["WWW-Authenticate"] = "Bearer " + ", ".join([*params, metadata, scope])
    return response


def unauthorized(invalid_token: bool = False) -> HttpResponse:
    return _challenge(
        HttpResponse(status=401), *(['error="invalid_token"'] if invalid_token else [])
    )


def insufficient_scope() -> HttpResponse:
    return _challenge(HttpResponse(status=403), 'error="insufficient_scope"')
