"""Teams that look like copies of each other, for their admins to merge.

A copy has the same name once case, spaces and punctuation are ignored. Pairs
an admin marked as different teams, and pairs that entered one event or
series, are never suggested: the merge would refuse the second anyway.
"""

import re
from collections import defaultdict

from django.db.models import Q

from server.core.models import Team, User
from server.duplicates.teams.merge import places_of
from server.duplicates.teams.models import TeamNotDuplicate
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType


def normalized_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def same_names() -> dict[str, list[Team]]:
    """Every name more than one team shares, with those teams."""
    # ponytail: reads every team's name; a normalized-name column once there are tens of thousands.
    groups: dict[str, list[Team]] = defaultdict(list)
    for team in Team.objects.order_by("pk"):
        if key := normalized_name(team.name):
            groups[key].append(team)
    return {key: teams for key, teams in groups.items() if len(teams) > 1}


def copies_of(team: Team, groups: dict[str, list[Team]] | None = None) -> list[Team]:
    same = [
        other
        for other in (groups if groups is not None else same_names()).get(
            normalized_name(team.name), []
        )
        if other.pk != team.pk
    ]
    if not same:
        return []
    ids = [other.pk for other in same]
    dismissed = set(
        TeamNotDuplicate.objects.filter(
            Q(team=team, other__in=ids) | Q(other=team, team__in=ids)
        ).values_list("team_id", "other_id")
    )
    taken = {pk for pair in dismissed for pk in pair} - {team.pk}
    where = places_of([team, *same])
    return [
        other for other in same if other.pk not in taken and not where[team.pk] & where[other.pk]
    ]


def suggestions_for(user: User, team_id: int | None = None) -> list[tuple[Team, list[Team]]]:
    """The teams this person admins that have likely copies, by name."""
    # Oldest first, so the copy named for a group is the one made first.
    teams = user.admin_teams.order_by("pk")
    if team_id is not None:
        teams = teams.filter(pk=team_id)
    groups = same_names()
    found, seen = [], set()
    for team in teams:
        # One per name: an admin of two copies gets one suggestion, not two.
        key = normalized_name(team.name)
        if key not in seen and (copies := copies_of(team, groups)):
            seen.add(key)
            found.append((team, copies))
    return sorted(found, key=lambda item: (item[0].name.casefold(), item[0].pk))


def merge_requested(teams: list[Team]) -> bool:
    """Staff already have a request to merge one of these teams."""
    return ServiceRequest.objects.filter(
        type=ServiceRequestType.REQUEST_TEAM_MERGE,
        status=ServiceRequestStatus.PENDING,
        service_teams__in=teams,
    ).exists()
