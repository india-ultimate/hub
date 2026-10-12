"""Refresh a tournament's cached pages whenever a row they show changes."""

import logging
from collections.abc import Callable, Iterable
from typing import Any

from django.db.models import Model, Q
from django.db.models.signals import m2m_changed, post_delete, post_save

from server.cache import store

log = logging.getLogger("server.cache")

# Each hooked model: how to find the tournaments a row of it shows on.
_FINDERS: dict[type[Model], Callable[[Any], Iterable[object]]] = {}
# Shown on the tournament lists too.
_LISTED: set[type[Model]] = set()


def _on_write(sender: type[Model], instance: Any, raw: bool = False, **kwargs: Any) -> None:
    if raw or not store.enabled():
        return
    try:
        for tid in _FINDERS[sender](instance):
            store.bump(str(tid))
        if sender in _LISTED:
            store.bump(store.ALL)
    except Exception:  # A save must never fail for the cache; the TTL catches up.
        log.warning("Couldn't refresh the public pages for %r", instance, exc_info=True)


def _on_teams_changed(
    sender: Any, instance: Any, action: str, pk_set: set[int] | None, **kwargs: Any
) -> None:
    """Tournament.teams or partial_teams, changed from either side."""
    if not store.enabled() or action not in ("post_add", "post_remove", "pre_clear", "post_clear"):
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
            store.bump(str(tid))
        store.bump(store.ALL)  # The lists carry each tournament's team ids.
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

    _FINDERS.update(
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
    _LISTED.update((Tournament, Event, Series))
    for model in _FINDERS:
        # The uids keep the old module's name, so they stay what they were.
        uid = f"public_cache:{model._meta.label}"
        post_save.connect(_on_write, sender=model, dispatch_uid=uid)
        # A deleted team leaves no join rows to find; its matches' deletes bump.
        if model is not Team:
            post_delete.connect(_on_write, sender=model, dispatch_uid=uid)
    for through in (Tournament.teams.through, Tournament.partial_teams.through):
        m2m_changed.connect(
            _on_teams_changed, sender=through, dispatch_uid=f"public_cache:{through._meta.label}"
        )
