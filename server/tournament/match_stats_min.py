from server.core.models import Player, Team
from server.tournament.models import Match, MatchEvent, MatchStats
from server.types import message_response

from .schema import MatchEventCreateSchema


def handle_all_events(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | dict[str, str]]:
    if match_event.type == MatchEvent.EventType.SCORE:
        return handle_score(match_event, match, team)
    elif match_event.type == MatchEvent.EventType.BLOCK:
        return handle_block(match_event, match, team)
    else:
        return 422, {"message": "Invalid event type"}


def handle_half_time(match: Match) -> tuple[int, MatchStats | dict[str, str]]:
    if match.team_1 is None or match.team_2 is None:
        return 422, {"message": "Invalid teams"}

    if match.stats.initial_possession.id == match.team_1.id:
        match.stats.current_possession = match.team_2
    elif match.stats.initial_possession.id == match.team_2.id:
        match.stats.current_possession = match.team_1

    match.stats.status = MatchStats.Status.SECOND_HALF
    match.stats.save()

    return 200, match.stats


def handle_full_time(match: Match) -> tuple[int, MatchStats | dict[str, str]]:
    match.stats.status = MatchStats.Status.COMPLETED
    match.stats.save()

    return 200, match.stats


def handle_switch_offense(match: Match) -> tuple[int, MatchStats | message_response]:
    if match.team_1 is None or match.team_2 is None:
        return 422, {"message": "Invalid teams"}

    if match.stats.current_possession.id == match.team_1.id:
        match.stats.current_possession = match.team_2
    elif match.stats.current_possession.id == match.team_2.id:
        match.stats.current_possession = match.team_1

    match.stats.save()
    return 200, match.stats


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

    if team.id != match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current possession"}

    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_1.id:
        match.stats.score_team_1 += 1
        match.stats.current_possession = match.team_2
    if match.team_1 is not None and match.team_2 is not None and team.id == match.team_2.id:
        match.stats.score_team_2 += 1
        match.stats.current_possession = match.team_1

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=MatchEvent.Mode.OFFENSE,  # ignore this for now, not used
        scored_by=scored_by,
        assisted_by=assisted_by,
        type=MatchEvent.EventType.SCORE,
        post_event_score_team_1=match.stats.score_team_1,
        post_event_score_team_2=match.stats.score_team_2,
    )
    new_match_event.save()

    score_sum = match.stats.score_team_1 + match.stats.score_team_2

    # Change ratio when sum of score is odd
    if score_sum % 2 == 1:
        if match.stats.current_ratio == MatchStats.GenderRatio.MALE:
            match.stats.current_ratio = MatchStats.GenderRatio.FEMALE
        elif match.stats.current_ratio == MatchStats.GenderRatio.FEMALE:
            match.stats.current_ratio = MatchStats.GenderRatio.MALE

    match.stats.save()

    return 200, match.stats


def handle_score_undo(
    match: Match, score_event: MatchEvent
) -> tuple[int, MatchStats | message_response]:
    if match.team_1 is None or match.team_2 is None:
        return 422, {"message": "Invalid teams"}

    if score_event.team.id == match.team_1.id:
        match.stats.score_team_1 -= 1
        match.stats.current_possession = match.team_1

    if score_event.team.id == match.team_2.id:
        match.stats.score_team_2 -= 1
        match.stats.current_possession = match.team_2

    score_sum = match.stats.score_team_1 + match.stats.score_team_2

    # Change ratio when sum of score is even (cause its undo match score)
    if score_sum % 2 == 0:
        if match.stats.current_ratio == MatchStats.GenderRatio.MALE:
            match.stats.current_ratio = MatchStats.GenderRatio.FEMALE
        elif match.stats.current_ratio == MatchStats.GenderRatio.FEMALE:
            match.stats.current_ratio = MatchStats.GenderRatio.MALE

    score_event.delete()
    match.stats.save()

    return 200, match.stats


def handle_block(
    match_event: MatchEventCreateSchema, match: Match, team: Team
) -> tuple[int, MatchStats | message_response]:
    if match_event.block_by_id is None:
        return 422, {"message": "Block by is needed"}

    try:
        block_by = Player.objects.get(id=match_event.block_by_id)
    except Player.DoesNotExist:
        return 422, {"message": "Invalid Block by"}

    if team.id == match.stats.current_possession.id:
        return 422, {"message": "Team does not match the team in current defense"}

    new_match_event = MatchEvent(
        stats=match.stats,
        team=team,
        started_on=MatchEvent.Mode.OFFENSE,  # ignore this for now, not used
        block_by=block_by,
        type=MatchEvent.EventType.BLOCK,
        post_event_score_team_1=match.stats.score_team_1,
        post_event_score_team_2=match.stats.score_team_2,
    )
    new_match_event.save()

    match.stats.current_possession = team
    match.stats.save()

    return 200, match.stats


def handle_block_undo(
    match: Match, block_event: MatchEvent
) -> tuple[int, MatchStats | message_response]:
    if match.team_1 is None or match.team_2 is None:
        return 422, {"message": "Invalid teams"}

    if block_event.team.id == match.team_1.id:
        match.stats.current_possession = match.team_2

    if block_event.team.id == match.team_2.id:
        match.stats.current_possession = match.team_1

    block_event.delete()
    match.stats.save()

    return 200, match.stats


def handle_undo(match: Match) -> tuple[int, MatchStats | message_response]:
    latest_events = MatchEvent.objects.filter(stats=match.stats).order_by("-time")

    if not latest_events:
        return 422, {"message": "No events to undo"}

    last_event = latest_events[0]

    if last_event.type == MatchEvent.EventType.SCORE:
        return handle_score_undo(match=match, score_event=last_event)
    elif last_event.type == MatchEvent.EventType.BLOCK:
        return handle_block_undo(match=match, block_event=last_event)
    else:
        return 422, {"message": "Invalid event type"}
