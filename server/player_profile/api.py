from typing import Any

from django.db.models import Count, Q
from django.http import HttpRequest
from ninja import Router

from server.core.models import CommentaryInfo, Player
from server.schema import Response
from server.tournament.models import Match, MatchEvent, MatchStats, Registration, Tournament
from server.types import message_response

from .schema import PlayerProfileSchema

router = Router()


def build_profile(player: Player) -> dict[str, Any]:
    registrations = list(
        Registration.objects.filter(player=player, event__tournament__isnull=False)
        .exclude(event__tournament__status=Tournament.Status.DRAFT)
        .select_related("event__tournament", "team")
        .order_by("-event__start_date", "-id")
    )
    ids = [r.event.tournament.id for r in registrations]

    event_counts = {
        row["stats__tournament_id"]: row
        for row in MatchEvent.objects.filter(stats__tournament_id__in=ids)
        .filter(Q(scored_by=player) | Q(assisted_by=player) | Q(block_by=player))
        .values("stats__tournament_id")
        .annotate(
            goals=Count(
                "id", filter=Q(type=MatchEvent.EventType.SCORE, scored_by=player), distinct=True
            ),
            assists=Count(
                "id", filter=Q(type=MatchEvent.EventType.SCORE, assisted_by=player), distinct=True
            ),
            blocks=Count(
                "id", filter=Q(type=MatchEvent.EventType.BLOCK, block_by=player), distinct=True
            ),
        )
    }
    games = dict(
        Match.objects.filter(stats__events__players=player, tournament_id__in=ids)
        .values_list("tournament_id")
        .annotate(n=Count("id", distinct=True))
    )
    tracked = set(
        MatchStats.objects.filter(tournament_id__in=ids)
        .values_list("tournament_id", flat=True)
        .distinct()
    )
    spirit = {
        row["tournament_id"]: row
        for row in Match.objects.filter(tournament_id__in=ids)
        .filter(
            Q(spirit_score_team_1__mvp_v2=player)
            | Q(spirit_score_team_2__mvp_v2=player)
            | Q(spirit_score_team_1__msp_v2=player)
            | Q(spirit_score_team_2__msp_v2=player)
        )
        .values("tournament_id")
        .annotate(
            mvp=Count(
                "id",
                filter=Q(spirit_score_team_1__mvp_v2=player)
                | Q(spirit_score_team_2__mvp_v2=player),
            ),
            msp=Count(
                "id",
                filter=Q(spirit_score_team_1__msp_v2=player)
                | Q(spirit_score_team_2__msp_v2=player),
            ),
        )
    }

    tournaments = []
    for r in registrations:
        t = r.event.tournament
        counts = event_counts.get(t.id, {})
        rank = next(
            (int(k) for k, team_id in (t.current_seeding or {}).items() if team_id == r.team_id),
            None,
        )
        tournaments.append(
            {
                "slug": r.event.slug,
                "title": r.event.title,
                "start_date": r.event.start_date,
                "end_date": r.event.end_date,
                "location": r.event.location,
                "logo_light": t.logo_light.url if t.logo_light else None,
                "logo_dark": t.logo_dark.url if t.logo_dark else None,
                "status": t.status,
                "team": r.team,
                "role": r.role,
                "is_playing": r.is_playing,
                "placement": rank if t.status == Tournament.Status.COMPLETED else None,
                "stats": (
                    {
                        "goals": counts.get("goals", 0),
                        "assists": counts.get("assists", 0),
                        "blocks": counts.get("blocks", 0),
                        "games": games.get(t.id, 0),
                    }
                    if t.id in tracked
                    else None
                ),
                "mvp": spirit.get(t.id, {}).get("mvp", 0),
                "msp": spirit.get(t.id, {}).get("msp", 0),
            }
        )

    try:
        jersey_number = player.commentary_info.jersey_number
    except CommentaryInfo.DoesNotExist:
        jersey_number = None
    return {
        "slug": player.slug,
        "full_name": player.user.get_full_name(),
        "profile_pic_url": player.profile_pic_url,
        "match_up": player.match_up,
        "state": player.get_state_ut_display() if player.state_ut else None,
        "jersey_number": jersey_number,
        "current_team": tournaments[0]["team"] if tournaments else None,
        "tournaments": tournaments,
    }


@router.get("/{slug}", auth=None, response={200: PlayerProfileSchema, 404: Response})
def get_profile(
    request: HttpRequest, slug: str
) -> tuple[int, dict[str, Any]] | tuple[int, message_response]:
    player = Player.objects.select_related("user", "commentary_info").filter(slug=slug).first()
    if player is None:
        return 404, {"message": "Player not found"}
    return 200, build_profile(player)
