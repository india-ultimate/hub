"""A cache, shared by every app machine, for the public tournament pages.

Each page belongs to one tournament, or to the lists of all of them, and is
kept for 30 s under that tournament's version. Any write to the tournament
bumps its version (see the receivers below), so the next GET is fresh. With
Redis unreachable every page is served from the database, as before.
"""

import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Any, TypeVar

from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, ResolverMatch, resolve

log = logging.getLogger(__name__)
T = TypeVar("T")

TTL = 30
LOOKUP_TTL = 24 * 60 * 60
ALL = "all"

# Every public tournament GET: none reads request.user, so every viewer
# gets the same body.
ROUTES = {
    "api/tournaments": ALL,
    "api/tournaments/public": ALL,
    "api/tournament": "query",
    "api/tournament/pools": "query",
    "api/tournament/cross-pool": "query",
    "api/tournament/brackets": "query",
    "api/tournament/position-pools": "query",
    "api/tournament/swiss-rounds": "query",
    "api/tournament/<tournament_id>/matches": "path",
    "api/tournament/<tournament_id>/fields": "path",
    "api/tournament/slug/<slug>/matches": "path",
    "api/tournament/slug/<slug>/fields": "path",
    "api/tournament/<tournament_slug>/team/<team_slug>/matches": "path",
    "api/tournament/<tournament_slug>/leaderboard": "path",
    "api/v1/tournament/<tournament_slug>/team/<team_slug>/roster": "path",
    "api/v2/tournament/<tournament_slug>/team/<team_slug>/roster": "path",
    "api/v2/tournament/<tournament_slug>/team/<team_slug>/roster-points": "path",
    "api/match/<match_id>": "path",
    "api/match/<match_id>/stats": "path",
}


def enabled() -> bool:
    # `cache` is a proxy that isinstance() can't see through.
    return not isinstance(caches["default"], DummyCache)


def safe(call: Callable[[], T], default: T) -> T:
    try:
        return call()
    except Exception:
        log.warning("Public page cache unavailable", exc_info=True)
        return default


def version_key(tid: str) -> str:
    return f"tver:{tid}"


def _looked_up(key: str, find: Callable[[], int | None]) -> str | None:
    found = cache.get(key)
    if found is None:
        tid = find()
        if tid is None:
            return None
        found = str(tid)
        cache.set(key, found, LOOKUP_TTL)
    return str(found)


def _id(value: object) -> str | None:
    """A positive integer in its one canonical spelling, else None."""
    try:
        number = int(str(value))
    except ValueError:
        return None
    return str(number) if number > 0 else None


def tournament_of(match: ResolverMatch, request: HttpRequest) -> str | None:
    """The tournament a public page belongs to, or ALL, or None if unknown.

    Reads the same input, in the same order, as the page's view.
    """
    from server.tournament.models import Match, Tournament

    kind = ROUTES[match.route]
    if kind == ALL:
        return ALL
    if "match_id" in match.kwargs:
        found_id = _id(match.kwargs["match_id"])
        if found_id is None:
            return None
        match_id: str = found_id
        return _looked_up(
            f"tmatch:{match_id}",
            lambda: Match.objects.filter(id=match_id)
            .values_list("tournament_id", flat=True)
            .first(),
        )
    if kind == "query":
        given = request.GET.get("id")
        # The pools view treats id=0 as missing; the others take any id.
        if given is not None and not (match.route == "api/tournament/pools" and given == "0"):
            return _id(given)
        slug = request.GET.get("slug")
    else:
        if "tournament_id" in match.kwargs:
            return _id(match.kwargs["tournament_id"])
        slug = match.kwargs.get("slug") or match.kwargs.get("tournament_slug")
    if not slug:
        return None
    name: str = slug
    return _looked_up(
        f"tslug:{name}",
        lambda: Tournament.objects.filter(event__slug=name).values_list("id", flat=True).first(),
    )


class PublicCacheMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tid = self.scope(request)
        if tid is None:
            return self.get_response(request)
        # Read once, before the view: a write during the view bumps past this
        # version, so what's stored under it can never hide the newer data.
        vkey = version_key(tid)
        version = safe(lambda: cache.get(vkey, 0), None)
        if version is None:  # The cache is down: one timeout per request, not three.
            return self.get_response(request)
        key = f"page:{tid}:{version}:{request.get_full_path()}"
        hit: Any = safe(lambda: cache.get(key), None)
        if hit is not None:
            body, content_type = hit
            return HttpResponse(body, content_type=content_type)
        response = self.get_response(request)
        if response.status_code == HTTPStatus.OK and not response.streaming:
            entry = (response.content, response["Content-Type"])
            safe(lambda: cache.set(key, entry, TTL), None)
        return response

    def scope(self, request: HttpRequest) -> str | None:
        if request.method != "GET" or not enabled():
            return None
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        if match.route not in ROUTES:
            return None
        return safe(lambda: tournament_of(match, request), None)
