import base64
import hashlib
import json
import logging
import time
from collections.abc import Callable
from functools import cache, wraps
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.views import AuthorizationView
from prometheus_client import Counter

from server.mcp import protocol
from server.mcp.auth import authenticate, has_bearer, unauthorized
from server.mcp.redirects import LOOPBACK_HOSTS

logger = logging.getLogger("server.mcp")
CALLS = Counter("hub_mcp_calls_total", "MCP tool calls", ["tool", "outcome"])
ORIGIN_HOSTS = {"claude.ai", "claude.com", "chatgpt.com"}


def enabled_only(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not settings.MCP_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper


@cache
def logo() -> str:
    mark = settings.BASE_DIR / "frontend" / "assets" / "iu-mark.png"
    return "data:image/png;base64," + base64.b64encode(mark.read_bytes()).decode()


class ConsentView(AuthorizationView):
    template_name = "mcp/consent.html"
    redirect_field_name = "redirect"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        context["logo"] = logo()
        application = context.get("application")
        if application:
            hosts = {urlparse(uri).hostname for uri in application.redirect_uris.split()}
            context["loopback_only"] = hosts <= LOOPBACK_HOSTS
            context["redirect_host"] = urlparse(context["redirect_uri"]).hostname
            # A metadata document's client_id is its own https address; a registered
            # client's name is only what it said about itself.
            client_id = application.client_id
            context["published_by"] = (
                urlparse(client_id).hostname if client_id.startswith("https://") else None
            )
        return context

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        posting = request.method == "POST"
        params = request.POST if posting else request.GET
        resources = params.getlist("resource")
        if any(resource != settings.MCP_RESOURCE_URL for resource in resources):
            logger.warning("Authorization refused: resource is not %s", settings.MCP_RESOURCE_URL)
            response = render(
                request, self.template_name, {"error": "invalid_target", "logo": logo()}, status=400
            )
        else:
            if not resources:
                defaulted = params.copy()
                defaulted["resource"] = settings.MCP_RESOURCE_URL
                setattr(request, "POST" if posting else "GET", defaulted)
            response = super().dispatch(request, *args, **kwargs)
        response["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response


def origin_allowed(request: HttpRequest) -> bool:
    origin = request.headers.get("Origin")
    if origin is None:
        return True
    parsed = urlparse(origin)
    return (
        parsed.hostname in LOOPBACK_HOSTS
        or (parsed.scheme == "https" and parsed.hostname in ORIGIN_HOSTS)
        or origin == settings.PUBLIC_URL
    )


@csrf_exempt
@enabled_only
def mcp(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        response = HttpResponse(status=405)
        response["Allow"] = "POST"
        return response
    if not origin_allowed(request):
        logger.warning("MCP request refused: Origin %s", request.headers.get("Origin", "")[:100])
        return HttpResponse(status=403)
    # Read the body before OAuth's form parsing can consume it.
    _ = request.body
    token = authenticate(request)
    if token is None:
        invalid = has_bearer(request)
        if invalid:
            logger.warning("MCP request refused: invalid or expired access token")
        return unauthorized(invalid)
    started = time.monotonic()
    audit: dict[str, Any] = {}
    response = protocol.handle(request, token, audit)
    outcome = audit.get("outcome", "ok")
    if tool := audit.get("tool"):
        CALLS.labels(tool, outcome).inc()
    canonical = json.dumps(audit.get("args"), sort_keys=True, separators=(",", ":"))
    logger.info(
        json.dumps(
            {
                "user_id": token.user.pk,
                "client_id": token.client_id,
                "method": audit.get("method"),
                "tool": tool,
                "args_digest": hashlib.sha256(canonical.encode()).hexdigest()[:16],
                "outcome": outcome,
                "ms": round((time.monotonic() - started) * 1000),
                **({"traceparent": audit["traceparent"]} if "traceparent" in audit else {}),
            }
        )
    )
    return response
