"""A cache, shared by every app machine, for the public tournament pages.

Each page belongs to one tournament, or to the lists of all of them, and is
kept for 30 s under that tournament's version. Any write to the tournament
bumps its version (see the receivers below), so the next GET is fresh. With
Redis unreachable every page is served from the database, as before.
"""

import logging
import time
from collections.abc import Callable, Iterable
from http import HTTPStatus
from typing import Any, TypeVar

from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.db import transaction
from django.db.models import Model, Q
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, ResolverMatch, resolve

log = logging.getLogger(__name__)
T = TypeVar("T")

TTL = 30
# A match never changes tournament, so its lookup can last. A slug can be
# recreated under a new id, so its lookup lasts no longer than a page.
MATCH_LOOKUP_TTL = 24 * 60 * 60
PAUSE = 5
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


_state = {"down_until": 0.0}


def reset() -> None:
    _state["down_until"] = 0.0


def enabled() -> bool:
    # `cache` is a proxy that isinstance() can't see through.
    return time.monotonic() >= _state["down_until"] and not isinstance(
        caches["default"], DummyCache
    )


def safe(call: Callable[[], T], default: T) -> T:
    if time.monotonic() < _state["down_until"]:
        return default
    try:
        return call()
    except Exception:
        # One slow or dead cache costs one timeout per process per PAUSE, not one per call.
        _state["down_until"] = time.monotonic() + PAUSE
        log.warning("Public page cache unavailable", exc_info=True)
        return default


def version_key(tid: str) -> str:
    return f"tver:{tid}"


def _looked_up(key: str, ttl: int, find: Callable[[], int | None]) -> str | None:
    found = cache.get(key)
    if found is None:
        tid = find()
        if tid is None:
            return None
        found = str(tid)
        cache.set(key, found, ttl)
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
            MATCH_LOOKUP_TTL,
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
        TTL,
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


def bump(tid: str) -> None:
    """Make every cached page of the tournament stale, once committed."""
    if not enabled():
        return

    def go() -> None:
        # A version only has to change, so one set does it.
        safe(lambda: cache.set(version_key(tid), time.time_ns(), None), None)

    transaction.on_commit(go)


# Each hooked model: how to find the tournaments a row of it shows on.
FINDERS: dict[type[Model], Callable[[Any], Iterable[object]]] = {}
# Shown on the tournament lists too.
LISTED: set[type[Model]] = set()


def on_write(sender: type[Model], instance: Any, raw: bool = False, **kwargs: Any) -> None:
    if raw or not enabled():
        return
    try:
        for tid in FINDERS[sender](instance):
            bump(str(tid))
        if sender in LISTED:
            bump(ALL)
    except Exception:  # A save must never fail for the cache; the TTL catches up.
        log.warning("Couldn't refresh the public pages for %r", instance, exc_info=True)


def on_teams_changed(
    sender: Any, instance: Any, action: str, pk_set: set[int] | None, **kwargs: Any
) -> None:
    """Tournament.teams or partial_teams, changed from either side."""
    if not enabled() or action not in ("post_add", "post_remove", "pre_clear", "post_clear"):
        return
    from server.tournament.models import Tournament

    try:
        tids: Iterable[object]
        if isinstance(instance, Tournament):
            tids = [] if action == "pre_clear" else [instance.pk]
        elif action == "pre_clear":  # A team's own list: by post_clear it's gone.
            tids = sender.objects.filter(team_id=instance.pk).values_list(
                "tournament_id", flat=True
            )
        else:
            tids = pk_set or ()
        for tid in tids:
            bump(str(tid))
        bump(ALL)  # The lists carry each tournament's team ids.
    except Exception:
        log.warning("Couldn't refresh the public pages for %r", instance, exc_info=True)


def connect() -> None:
    """Hook every write that changes a public tournament page."""
    from server.core.models import Team
    from server.series.models import Series
    from server.tournament.models import (
        Bracket,
        CrossPool,
        Event,
        Match,
        MatchEvent,
        MatchScore,
        MatchStats,
        Pool,
        PositionPool,
        Registration,
        SpiritScore,
        SwissRound,
        Tournament,
        TournamentField,
        UCRegistration,
    )

    def own(row: Any) -> list[object]:
        return [row.tournament_id]

    def by_event(row: Any) -> Iterable[object]:
        return Tournament.objects.filter(event_id=row.event_id).values_list("id", flat=True)

    def matches(*fields: str) -> Callable[[Any], Iterable[object]]:
        def find(row: Any) -> Iterable[object]:
            q = Q()
            for field in fields:
                q |= Q(**{field: row})
            return Match.objects.filter(q).values_list("tournament_id", flat=True)

        return find

    FINDERS.update(
        {
            Tournament: lambda t: [t.pk],
            Event: lambda e: Tournament.objects.filter(event_id=e.pk).values_list("id", flat=True),
            Series: lambda s: Tournament.objects.filter(event__series_id=s.pk).values_list(
                "id", flat=True
            ),
            **dict.fromkeys(
                (
                    Match,
                    Pool,
                    CrossPool,
                    Bracket,
                    PositionPool,
                    SwissRound,
                    TournamentField,
                    MatchStats,
                ),
                own,
            ),
            MatchEvent: lambda e: MatchStats.objects.filter(id=e.stats_id).values_list(
                "tournament_id", flat=True
            ),
            MatchScore: matches("suggested_score_team_1", "suggested_score_team_2"),
            SpiritScore: matches(
                "spirit_score_team_1",
                "spirit_score_team_2",
                "self_spirit_score_team_1",
                "self_spirit_score_team_2",
            ),
            Registration: by_event,
            UCRegistration: by_event,
            Team: lambda t: Tournament.objects.filter(Q(teams=t) | Q(partial_teams=t))
            .values_list("id", flat=True)
            .distinct(),
        }
    )
    LISTED.update((Tournament, Event, Series))
    for model in FINDERS:
        uid = f"public_cache:{model._meta.label}"
        post_save.connect(on_write, sender=model, dispatch_uid=uid)
        # A deleted team leaves no join rows to find; its matches' deletes bump.
        if model is not Team:
            post_delete.connect(on_write, sender=model, dispatch_uid=uid)
    for through in (Tournament.teams.through, Tournament.partial_teams.through):
        m2m_changed.connect(
            on_teams_changed, sender=through, dispatch_uid=f"public_cache:{through._meta.label}"
        )
