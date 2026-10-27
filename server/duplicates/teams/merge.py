"""Folding duplicate teams into the one staff choose to keep.

Foreign keys move with the account merge's relation walk. Many-to-manys are
repointed in their join tables, because Tournament.teams.add() fires a receiver
that re-enumerates the tournament's seeding. Tournaments also keep team ids
inside JSON (seeding, standings, byes, spirit ranking), which no relation
reaches, so those are rewritten field by field.

Two teams that were both at one event or in one series are refused: they played
each other or were separate squads, and their rows there would collide.
"""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from django.core.serializers import serialize
from django.db import transaction
from django.db.models import Model, Q
from django.db.models.fields.reverse_related import ManyToManyRel

from server.cache import store
from server.core.models import Team, User
from server.duplicates.relations import (
    MergeIncompleteError,
    fill_blanks,
    inbound_relations,
    move_rows,
    references_to,
    relation_label,
)
from server.duplicates.teams.models import TeamMerge
from server.registration.models import RosterEntry, RosterSwap
from server.series.models import Series, SeriesRegistration, SeriesRosterInvitation
from server.tournament.models import (
    Bracket,
    CrossPool,
    Event,
    EventRosterInvitation,
    Match,
    Pool,
    PositionPool,
    Registration,
    SwissRound,
    Tournament,
    UCRegistration,
)

# Filled from an absorbed team only where the keeper has nothing.
TEAM_FILLABLE = ("image", "image_url", "facebook_url", "city", "state_ut", "ultimate_central_id")

# Every JSON field holding team ids, by model. Seedings and byes map to a team,
# standings tables are keyed by one, spirit ranking lists them.
JSON_FIELDS: dict[type[Model], tuple[str, ...]] = {
    Tournament: ("initial_seeding", "current_seeding", "spirit_ranking"),
    Pool: ("initial_seeding", "results"),
    PositionPool: ("initial_seeding", "results"),
    SwissRound: ("initial_seeding", "results", "round_results", "byes"),
    CrossPool: ("initial_seeding", "current_seeding"),
    Bracket: ("initial_seeding", "current_seeding"),
}


class TeamMergeBlockedError(Exception):
    """The teams must not be merged. args[0] says why, in words."""


def _table(table: dict[str, Any], swap: Callable[[Any], Any]) -> dict[str, Any]:
    return {
        str(swap(key)): (
            {**row, "id": swap(row["id"])} if isinstance(row, dict) and "id" in row else row
        )
        for key, row in (table or {}).items()
    }


def _mapped(values: dict[str, Any], swap: Callable[[Any], Any]) -> dict[str, Any]:
    """The JSON fields with swap applied to every team id, and nothing else.

    Structural on purpose: a score of 15 must not become a team because team 15
    is being merged.
    """
    out: dict[str, Any] = {}
    for name, value in values.items():
        if name == "results":
            out[name] = _table(value, swap)
        elif name == "round_results":
            out[name] = {r: _table(table, swap) for r, table in (value or {}).items()}
        elif name == "spirit_ranking":
            out[name] = [
                {**row, "team_id": swap(row["team_id"])} if "team_id" in row else row
                for row in value or []
            ]
        else:
            out[name] = {key: swap(team) for key, team in (value or {}).items()}
    return out


def _json_rows() -> Iterator[tuple[type[Model], int, int, dict[str, Any]]]:
    """(model, pk, event id, JSON fields) for every row holding team ids."""
    # ponytail: reads every tournament and stage per merge; filter by a JSON
    # lookup if that ever grows past a few thousand rows.
    for model, names in JSON_FIELDS.items():
        event = "event_id" if model is Tournament else "tournament__event_id"
        for row in model._default_manager.values("pk", event, *names):
            yield model, row["pk"], row[event], {name: row[name] for name in names}


def _ids_in(values: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def note(team: Any) -> Any:
        found.add(str(team))
        return team

    _mapped(values, note)
    return found


def _places(teams: list[Team]) -> dict[int, set[tuple[str, int]]]:
    """Every event and series each team took part in, by team id."""
    ids = [team.pk for team in teams]
    places: dict[int, set[tuple[str, int]]] = {pk: set() for pk in ids}

    def add(kind: str, rows: Any) -> None:
        for team_id, place in rows:
            if team_id in places and place is not None:
                places[team_id].add((kind, place))

    for model in (Registration, RosterEntry, RosterSwap, UCRegistration, EventRosterInvitation):
        add("event", model.objects.filter(team__in=ids).values_list("team_id", "event_id"))
    for through in (Tournament.teams.through, Tournament.partial_teams.through):
        add(
            "event",
            through.objects.filter(team__in=ids).values_list("team_id", "tournament__event_id"),
        )
    for side in ("team_1", "team_2"):
        add(
            "event",
            Match.objects.filter(**{f"{side}__in": ids}).values_list(
                f"{side}_id", "tournament__event_id"
            ),
        )
    wanted = {str(pk): pk for pk in ids}
    for _, _, event_id, values in _json_rows():
        for found in _ids_in(values) & wanted.keys():
            places[wanted[found]].add(("event", event_id))

    add(
        "series",
        Series.teams.through.objects.filter(team__in=ids).values_list("team_id", "series_id"),
    )
    for model in (SeriesRegistration, SeriesRosterInvitation):
        add("series", model.objects.filter(team__in=ids).values_list("team_id", "series_id"))
    return places


def label(team: Team) -> str:
    return f"{team.name.strip()} #{team.pk}"


def blockers(teams: list[Team], places: dict[int, set[tuple[str, int]]] | None = None) -> list[str]:
    """Why these teams cannot be one, in words. Empty if they can."""
    places = places if places is not None else _places(teams)
    events = dict(Event.objects.values_list("id", "title"))
    series = dict(Series.objects.values_list("id", "name"))
    found = []
    for a, b in combinations(teams, 2):
        for kind, place in sorted(places[a.pk] & places[b.pk]):
            where = (
                f"at {events.get(place, 'an event')}"
                if kind == "event"
                else (f"in {series.get(place, 'a series')}")
            )
            found.append(f"{label(a)} and {label(b)} were both {where}")
    return found


def _move_links(rel: ManyToManyRel, source: Team, target: Team) -> int:
    """Repoint a many-to-many at target in its join table, skipping signals."""
    through: Any = rel.through
    team, other = rel.field.m2m_reverse_field_name(), rel.field.m2m_field_name()
    rows = through.objects.filter(**{team: source})
    count = rows.count()
    held = through.objects.filter(**{team: target}).values_list(f"{other}_id", flat=True)
    rows.filter(**{f"{other}_id__in": list(held)}).delete()
    rows.update(**{team: target})
    return count


def _rewrite_json(source: Team, target: Team) -> set[int]:
    """Point every JSON team id at target. Returns the events touched."""
    events = set()

    def swap(team: Any) -> Any:
        return type(team)(target.pk) if str(team) == str(source.pk) else team

    for model, pk, event_id, values in _json_rows():
        if str(source.pk) in _ids_in(values):
            model._default_manager.filter(pk=pk).update(**_mapped(values, swap))
            events.add(event_id)
    return events


def merge_teams(keeper: Team, others: list[Team], actor: User | None = None) -> TeamMerge:
    """Fold others into keeper, then delete them."""
    with transaction.atomic():
        # Ordered by pk so two merges sharing a team cannot deadlock.
        locked = {
            team.pk: team
            for team in Team.objects.select_for_update()
            .filter(pk__in=[keeper.pk, *(team.pk for team in others)])
            .order_by("pk")
        }
        absorbed = [team for pk, team in locked.items() if pk != keeper.pk]
        if keeper.pk not in locked or not absorbed:
            raise TeamMergeBlockedError(["Pick a team to keep and at least one to merge into it"])
        keeper = locked[keeper.pk]

        places = _places([keeper, *absorbed])
        problems = blockers([keeper, *absorbed], places)
        if problems:
            raise TeamMergeBlockedError(problems)

        snapshot = json.loads(serialize("json", absorbed))
        moved: dict[str, int] = {}
        events = {place for team in places.values() for kind, place in team if kind == "event"}
        for team in absorbed:
            events |= _rewrite_json(team, keeper)
            for rel in inbound_relations(Team):
                if isinstance(rel, ManyToManyRel):
                    count = _move_links(rel, team, keeper)
                else:
                    count, lost = move_rows(rel, team, keeper)
                    if lost:  # The blockers rule this out; never delete a row to fit.
                        raise MergeIncompleteError({relation_label(rel): len(lost)})
                if count:
                    moved[relation_label(rel)] = moved.get(relation_label(rel), 0) + count
            keeper.admins.add(*team.admins.all())

            stuck = references_to(Team, [team])
            if stuck:
                raise MergeIncompleteError(stuck)

        merge = TeamMerge.objects.create(
            keeper=keeper,
            merged_by=actor,
            absorbed_team_ids=[team.pk for team in absorbed],
            moved=moved,
            snapshot=snapshot,
        )
        for team in absorbed:
            team.delete()
        # After the deletes: ultimate_central_id is unique.
        for team in absorbed:
            fill_blanks(keeper, team, TEAM_FILLABLE)

        # Queryset updates fire no signals, so the public pages are told here.
        for tid in Tournament.objects.filter(event_id__in=events).values_list("id", flat=True):
            store.bump(str(tid))
        store.bump(store.ALL)
    return merge


@dataclass(frozen=True)
class Line:
    label: str
    values: list[str]
    # Only rows that say who a team is; a blank is unknown, not different.
    identity: bool = False

    @property
    def differs(self) -> bool:
        if not self.identity:
            return False
        values = {value for value in self.values if value}
        if self.label == "Name":
            # Spacing aside: the kept name is the one that survives, case and all.
            values = {" ".join(value.split()) for value in values}
        return len(values) > 1


def _usage(team: Team) -> dict[str, int]:
    return {
        "Tournaments": team.tournaments.count(),
        "Registrations": Registration.objects.filter(team=team).count(),
        "Series": team.series.count(),
        "Matches": Match.objects.filter(Q(team_1=team) | Q(team_2=team)).count(),
        "Players": team.players.count(),
        "Admins": team.admins.count(),
    }


def default_keeper(teams: list[Team]) -> Team:
    """The most used: tournaments, then registrations, then the oldest."""

    def rank(team: Team) -> tuple[int, int, int]:
        usage = _usage(team)
        return usage["Tournaments"], usage["Registrations"], -team.pk

    return max(teams, key=rank)


def compare(teams: list[Team]) -> list[Line]:
    usage = [_usage(team) for team in teams]
    return [
        Line("Name", [team.name for team in teams], identity=True),
        Line("Category", [team.category for team in teams], identity=True),
        Line("City", [team.city or "" for team in teams], identity=True),
        Line(
            "State",
            [team.get_state_ut_display() if team.state_ut else "" for team in teams],
            identity=True,
        ),
        Line("Web address", [team.slug or "" for team in teams]),
        Line("Ultimate Central ID", [str(team.ultimate_central_id or "") for team in teams]),
        *(Line(label, [str(row[label]) for row in usage]) for label in usage[0]),
    ]
