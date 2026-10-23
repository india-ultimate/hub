import json
from typing import Any
from urllib.parse import urlsplit

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from oauth2_provider import cimd
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher
from oauth2_provider.views import (
    DynamicClientRegistrationManagementView,
    DynamicClientRegistrationView,
)

from server.cache.store import FailOpenCache, safe
from server.core.otp import client_ip

# Hosted agents' own callbacks. Agents that run on the person's computer use loopback.
HOSTED_CALLBACKS = {
    "https://claude.ai/api/mcp/auth_callback",
    "https://chatgpt.com/connector_platform_oauth_redirect",
}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
GRANT_TYPES = {"authorization_code", "refresh_token"}
RESPONSE_TYPES = {"code"}
REGISTRATIONS_PER_WINDOW = 10
REGISTRATION_WINDOW = 60 * 60


def redirect_allowed(uri: object) -> bool:
    if not isinstance(uri, str) or not uri:
        return False
    if any(char.isspace() or not char.isprintable() for char in uri):
        return False
    if uri in HOSTED_CALLBACKS:
        return True
    parts = urlsplit(uri)
    return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS


def disallowed(uris: object) -> list[str]:
    if not isinstance(uris, list):
        return ["redirect_uris must be a list"]
    return [str(uri) for uri in uris if not redirect_allowed(uri)]


def _outside(values: object, allowed: set[str]) -> bool:
    return not isinstance(values, list) or any(
        not isinstance(value, str) or value not in allowed for value in values
    )


def unsupported(metadata: dict[str, Any]) -> bool:
    return _outside(metadata.get("grant_types", []), GRANT_TYPES) or _outside(
        metadata.get("response_types", []), RESPONSE_TYPES
    )


def as_public_client(metadata: dict[str, Any]) -> dict[str, Any]:
    """An agent's metadata document as the public, authorization-code client Hub has it
    sign in as. Agents list more than they use here: Claude names a jwt-bearer grant too,
    and ChatGPT says it signs with private_key_jwt but supports none, which is all Hub
    offers. Grants Hub doesn't offer are left out, so nothing can use them."""
    grants = metadata.get("grant_types", ["authorization_code"])
    if isinstance(grants, list) and "authorization_code" in grants:
        metadata = {**metadata, "grant_types": [g for g in grants if g in GRANT_TYPES]}
    methods = metadata.get("token_endpoint_auth_methods_supported")
    if isinstance(methods, list) and "none" in methods:
        metadata = {**metadata, "token_endpoint_auth_method": "none"}
    return metadata


def fail_open() -> None:
    # The library only notes which documents failed lately: a slow or restarting
    # Redis should mean fetching again, not a failed sign-in.
    cimd.cache = FailOpenCache()


class PolicyMetadataFetcher(SafeMetadataFetcher):
    def fetch(self, client_id: str) -> Any:
        metadata, max_age = super().fetch(client_id)
        if disallowed(metadata.get("redirect_uris")):
            raise CIMDError("redirect_uris must be a known AI agent callback or loopback")
        metadata = as_public_client(metadata)
        if unsupported(metadata):
            raise CIMDError("Only the authorization_code and refresh_token grants are supported")
        return metadata, max_age


def _refusal(request: HttpRequest) -> HttpResponse | None:
    try:
        metadata = json.loads(request.body)
        bad = disallowed(metadata.get("redirect_uris"))
    except (ValueError, AttributeError):
        return None
    if unsupported(metadata):
        return JsonResponse(
            {
                "error": "invalid_client_metadata",
                "error_description": (
                    "Only grant_types authorization_code and refresh_token, "
                    "and response_types code, are supported."
                ),
            },
            status=400,
        )
    if not bad:
        return None
    return JsonResponse(
        {
            "error": "invalid_redirect_uri",
            "error_description": (
                f"Not allowed: {', '.join(bad)}. Use a hosted agent's callback "
                f"({', '.join(sorted(HOSTED_CALLBACKS))}) "
                "or an http loopback address (localhost, 127.0.0.1, [::1])."
            ),
        },
        status=400,
    )


def _registration_limited(request: HttpRequest) -> bool:
    key = f"mcp-dcr:{client_ip(request)}"

    def count() -> bool:
        cache.add(key, 0, REGISTRATION_WINDOW)
        try:
            return bool(cache.incr(key) > REGISTRATIONS_PER_WINDOW)
        except ValueError:
            return False

    return safe(count, False)


class RegistrationView(DynamicClientRegistrationView):
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if _registration_limited(request):
            return JsonResponse(
                {
                    "error": "temporarily_unavailable",
                    "error_description": "Too many registrations from this address. Try later.",
                },
                status=429,
            )
        return _refusal(request) or super().post(request, *args, **kwargs)


class RegistrationManagementView(DynamicClientRegistrationManagementView):
    def put(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        return _refusal(request) or super().put(request, *args, **kwargs)
