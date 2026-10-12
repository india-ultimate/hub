"""Serve and store the public tournament pages."""

from collections.abc import Callable
from http import HTTPStatus

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve

from server.cache import routes, store


class PublicCacheMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tid = self._scope(request)
        if tid is None:
            return self.get_response(request)
        # Read once, before the view: a write during the view bumps past this
        # version, so what's stored under it can never hide the newer data.
        version = store.version(tid)
        if version is None:  # The cache is down: one timeout per request, not three.
            return self.get_response(request)
        path = request.get_full_path()
        hit = store.get_page(tid, version, path)
        if hit is not None:
            body, content_type = hit
            return HttpResponse(body, content_type=content_type)
        response = self.get_response(request)
        if response.status_code == HTTPStatus.OK and not response.streaming:
            store.set_page(tid, version, path, response.content, response["Content-Type"])
        return response

    def _scope(self, request: HttpRequest) -> str | None:
        if request.method != "GET" or not store.enabled():
            return None
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        return store.safe(lambda: routes.scope(match, request), None)
