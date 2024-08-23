from server.core.models import Player, Team
from server.tournament.models import Match, MatchEvent, MatchStats

from .schema import MatchEventCreateSchema


def handle_all_events(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.type == MatchEvent.EventType.LINE_SELECTED:
        return handle_line_selected(match_event, match, team)
    elif match_event.type == MatchEvent.EventType.SCORE:
        return handle_score(match_event, match, team)
    elif match_event.type == MatchEvent.EventType.DROP:
        return handle_drop(match_event, match, team)
    elif match_event.type == MatchEvent.EventType.THROWAWAY:
        return handle_throwaway(match_event, match, team)
    elif match_event.type == MatchEvent.EventType.BLOCK:
        return handle_block(match_event, match, team)
    else:
        return 422, {"message": "Invalid event type"}


def handle_half_time(match: Match) -> tuple[int, MatchStats | dict[str, str]]:
    if (
        match.team_1 is not None
        and match.team_2 is not None
        and match.team_1.id == match.stats.initial_possession
    ):
        match.stats.current_possession = match.team_2
    elif (
        match.team_1 is not None
        and match.team_2 is not None
        and match.team_2.id == match.stats.initial_possession
    ):
        match.stats.current_possession = match.team_1

    match.stats.status = MatchStats.Status.SECOND_HALF
    match.stats.save()

    return 200, match.stats


def handle_full_time(match: Match) -> tuple[int, MatchStats | dict[str, str]]:
    match.stats.status = MatchStats.Status.COMPLETED
    match.stats.save()

    return 200, match.stats


def handle_line_selected(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.player_ids is None or len(match_event.player_ids) == 0:
        return 422, {"message": "No players exist for line selected event"}

    if match.team_1 is not None and team.id == match.team_1.id:
        if match.stats.status_team_1 != MatchStats.TeamStatus.PENDING_LINE_SELECTION:
            return 422, {
                "message": "Cant add players in any others state that pending line selection"
            }

        players = Player.objects.filter(pk__in=match_event.player_ids)

        team_with_possession = match.stats.current_possession
        mode = (
            MatchEvent.Mode.OFFENSE
            if team.id == team_with_possession.id
            else MatchEvent.Mode.DEFENSE
        )

        new_match_event = MatchEvent(
            stats=match.stats, team=team, started_on=mode, type=MatchEvent.EventType.LINE_SELECTED
        )
        new_match_event.save()

        for player in players:
            new_match_event.players.add(player)

        match.stats.status_team_1 = MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        match.stats.save()

        return 200, match.stats
    if match.team_2 is not None and team.id == match.team_2.id:
        if match.stats.status_team_2 != MatchStats.TeamStatus.PENDING_LINE_SELECTION:
            return 422, {
                "message": "Cant add players in any others state that pending line selection"
            }

        players = Player.objects.filter(pk__in=match_event.player_ids)

        team_with_possession = match.stats.current_possession
        mode = (
            MatchEvent.Mode.OFFENSE if team.id == team_with_possession else MatchEvent.Mode.DEFENSE
        )

        new_match_event = MatchEvent(
            stats=match.stats, team=team, started_on=mode, type=MatchEvent.EventType.LINE_SELECTED
        )
        new_match_event.save()

        for player in players:
            new_match_event.players.add(player)

        match.stats.status_team_2 = MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        match.stats.save()

        return 200, match.stats

    return 422, {"message": "Team not present in match"}


def handle_score(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.scored_by_id is None or match_event.assisted_by_id is None:
        return 422, {"message": "Scored by and assisted by is needed"}

    try:
        scored_by = Player.objects.get(id=match_event.scored_by_id)
        assisted_by = Player.objects.get(id=match_event.assisted_by_id)
    except Player.DoesNotExist:
        return 422, {"message": "Invalid Scored by or assisted by"}

    if (
        match.stats.status_team_1 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        or match.stats.status_team_2 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    ):
        return 422, {"message": "Lines are not selected in either teams"}

    if team.id != match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current possession"}

    latest_line_selection_event = MatchEvent.objects.filter(
        stats=match.stats, team=team, type=MatchEvent.EventType.LINE_SELECTED
    ).order_by("-time")[0]

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=latest_line_selection_event.started_on,
        scored_by=scored_by,
        assisted_by=assisted_by,
        type=MatchEvent.EventType.SCORE,
    )
    new_match_event.save()

    for player in latest_line_selection_event.players.all():
        new_match_event.players.add(player)

    match.stats.status_team_1 = MatchStats.TeamStatus.PENDING_LINE_SELECTION
    match.stats.status_team_2 = MatchStats.TeamStatus.PENDING_LINE_SELECTION

    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_1.id:
        match.stats.score_team_1 += 1
        match.stats.current_possession = match.team_2
    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_2.id:
        match.stats.score_team_2 += 1
        match.stats.current_possession = match.team_1

    match.stats.save()

    return 200, match.stats


def handle_drop(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.drop_by_id is None:
        return 422, {"message": "Drop by is needed"}

    try:
        drop_by = Player.objects.get(id=match_event.drop_by_id)
    except Player.DoesNotExist:
        return 422, {"message": "Invalid Drop by"}

    if (
        match.stats.status_team_1 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        or match.stats.status_team_2 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    ):
        return 422, {"message": "Lines are not selected in either teams"}

    if team.id != match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current possession"}

    latest_line_selection_event = MatchEvent.objects.filter(
        stats=match.stats, team=team, type=MatchEvent.EventType.LINE_SELECTED
    ).order_by("-time")[0]

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=latest_line_selection_event.started_on,
        drop_by=drop_by,
        type=MatchEvent.EventType.DROP,
    )
    new_match_event.save()

    for player in latest_line_selection_event.players.all():
        new_match_event.players.add(player)

    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_1.id:
        match.stats.current_possession = match.team_2
    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_2.id:
        match.stats.current_possession = match.team_1

    match.stats.save()

    return 200, match.stats


def handle_throwaway(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.throwaway_by_id is None:
        return 422, {"message": "Throwaway by is needed"}

    try:
        throwaway_by = Player.objects.get(id=match_event.throwaway_by_id)
    except Player.DoesNotExist:
        return 422, {"message": "Invalid Throwaway by"}

    if (
        match.stats.status_team_1 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        or match.stats.status_team_2 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    ):
        return 422, {"message": "Lines are not selected in either teams"}

    if team.id != match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current possession"}

    latest_line_selection_event = MatchEvent.objects.filter(
        stats=match.stats, team=team, type=MatchEvent.EventType.LINE_SELECTED
    ).order_by("-time")[0]

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=latest_line_selection_event.started_on,
        throwaway_by=throwaway_by,
        type=MatchEvent.EventType.THROWAWAY,
    )
    new_match_event.save()

    for player in latest_line_selection_event.players.all():
        new_match_event.players.add(player)

    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_1.id:
        match.stats.current_possession = match.team_2
    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_2.id:
        match.stats.current_possession = match.team_1

    match.stats.save()

    return 200, match.stats


def handle_block(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.block_by_id is None:
        return 422, {"message": "Block by is needed"}

    try:
        block_by = Player.objects.get(id=match_event.block_by_id)
    except Player.DoesNotExist:
        return 422, {"message": "Invalid Block by"}

    if (
        match.stats.status_team_1 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
        or match.stats.status_team_2 != MatchStats.TeamStatus.COMPLETED_LINE_SELECTION
    ):
        return 422, {"message": "Lines are not selected in either teams"}

    if team.id == match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current defense"}

    latest_line_selection_event = MatchEvent.objects.filter(
        stats=match.stats, team=team, type=MatchEvent.EventType.LINE_SELECTED
    ).order_by("-time")[0]

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=latest_line_selection_event.started_on,
        block_by=block_by,
        type=MatchEvent.EventType.BLOCK,
    )
    new_match_event.save()

    for player in latest_line_selection_event.players.all():
        new_match_event.players.add(player)

    if match.team_1 is not None and match.team_1.id == team.id:
        match.stats.current_possession = team
    if match.team_2 is not None and match.team_2.id == team.id:
        match.stats.current_possession = team

    match.stats.save()

    return 200, match.stats
