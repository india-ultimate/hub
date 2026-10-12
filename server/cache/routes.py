"""Which public pages are cached, and which tournament each belongs to."""

from django.http import HttpRequest
from django.urls import ResolverMatch

from server.cache import store

# Every public tournament GET: none reads request.user, so every viewer
# gets the same body.
ROUTES = {
    "api/tournaments": store.ALL,
    "api/tournaments/public": store.ALL,
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


def _id(value: object) -> str | None:
    """A positive integer in its one canonical spelling, else None."""
    try:
        number = int(str(value))
    except ValueError:
        return None
    return str(number) if number > 0 else None


def scope(match: ResolverMatch, request: HttpRequest) -> str | None:
    """The tournament a public page belongs to, or ALL, or None if unknown or not cached.

    Reads the same input, in the same order, as the page's view. It can raise
    on a database or a malformed request, which the view will report itself.
    """
    if match.route not in ROUTES:
        return None
    from server.tournament.models import Match, Tournament

    kind = ROUTES[match.route]
    if kind == store.ALL:
        return store.ALL
    if "match_id" in match.kwargs:
        found_id = _id(match.kwargs["match_id"])
        if found_id is None:
            return None
        match_id: str = found_id
        return store.match_tournament(
            match_id,
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
    return store.slug_tournament(
        name,
        lambda: Tournament.objects.filter(event__slug=name).values_list("id", flat=True).first(),
    )
