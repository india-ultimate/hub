import contextlib
import json
import re
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.http import Http404, HttpResponse
from django.test.client import BOUNDARY, MULTIPART_CONTENT, RequestFactory, encode_multipart
from django.urls import Resolver404, resolve

from server.mcp.registry import ToolContext, ToolResult, fail

API_PATH = re.compile(r"/api/[A-Za-z0-9/_\-.]*")


@dataclass
class ApiResponse:
    status: int
    data: Any

    @property
    def ok(self) -> bool:
        return HTTPStatus.OK <= self.status < HTTPStatus.MULTIPLE_CHOICES

    @property
    def message(self) -> str:
        if isinstance(self.data, dict) and isinstance(self.data.get("message"), str):
            return self.data["message"]
        return f"Hub answered {self.status}"


def refuse(reason: str) -> ToolResult:
    return fail(f"Not allowed: {reason}")


def denied(response: ApiResponse, not_found: str | None = None) -> ToolResult:
    if response.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        return refuse(response.message)
    if not_found and response.status == HTTPStatus.NOT_FOUND:
        return fail(not_found)
    return fail(response.message)


def call_api(
    ctx: ToolContext,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    files: dict[str, UploadedFile] | None = None,
) -> ApiResponse:
    if not API_PATH.fullmatch(path) or ".." in path:
        raise ValueError(f"Not an API path: {path!r}")
    if files is not None:
        data: str | bytes = encode_multipart(BOUNDARY, {**(body or {}), **files})
        content_type = MULTIPART_CONTENT
    elif body is not None:
        data, content_type = json.dumps(body), "application/json"
    else:
        data, content_type = "", "application/octet-stream"
    sub = RequestFactory().generic(
        method, path, data, content_type, query_params=query, headers={"Accept": "application/json"}
    )
    sub.user = ctx.user
    sub._dont_enforce_csrf_checks = True  # type: ignore[attr-defined]
    sub.session = SessionStore()
    sub.environ["wsgi.url_scheme"] = ctx.outer.scheme
    for header in ("REMOTE_ADDR", "HTTP_FLY_CLIENT_IP", "HTTP_HOST", "SERVER_NAME", "SERVER_PORT"):
        if header in ctx.outer.META:
            sub.META[header] = ctx.outer.META[header]
    try:
        match = resolve(path)
    except Resolver404:
        return ApiResponse(404, {"message": "Not found"})
    try:
        response: HttpResponse = match.func(sub, *match.args, **match.kwargs)
    except Http404 as error:
        return ApiResponse(404, {"message": str(error) or "Not found"})
    except PermissionDenied as error:
        return ApiResponse(403, {"message": str(error) or "Permission denied"})
    payload = None
    if not response.streaming:
        with contextlib.suppress(ValueError):
            payload = json.loads(response.content)
    return ApiResponse(response.status_code, payload)
