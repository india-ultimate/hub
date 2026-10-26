from collections import Counter
from typing import Any

from django.db.models import Count, Q
from django.http import HttpRequest
from ninja import Router

from server.core.models import CommentaryInfo, Player, Team
from server.schema import Response
from server.season.models import Season
from server.series.models import PLAYING_ROLES
from server.tournament.models import Match, MatchEvent, MatchStats, Registration, Tournament
from server.types import message_response
from server.utils import full_name, today

from .schema import PlayerProfileSchema

router = Router()


def _season_team(registrations: list[Registration]) -> tuple[Registration, str] | None:
    season = Season.containing(today())
    if season is None:
        return None
    reg = next(
        (r for r in registrations if season.start_date <= r.event.start_date <= season.end_date),
        None,
    )
    if reg is None:
        return None
    return reg, season.label


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
    appearances = [
        MatchEvent.objects.filter(stats__tournament_id__in=ids, **{field: player}).values_list(
            "stats__match_id", "stats__tournament_id"
        )
        for field in (
            "players",
            "scored_by",
            "assisted_by",
            "block_by",
            "drop_by",
            "throwaway_by",
        )
    ]
    games = Counter(tournament_id for _, tournament_id in appearances[0].union(*appearances[1:]))
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
    season_team = _season_team(registrations)
    honour = next(
        (
            r
            for r in registrations
            if r.role in PLAYING_ROLES and r.team.category == Team.CategoryTypes.STATE
        ),
        None,
    )
    return {
        "slug": player.slug,
        "full_name": full_name(player.user),
        "profile_pic_url": player.profile_pic_url,
        "match_up": player.match_up,
        "state": player.get_state_ut_display() if player.state_ut else None,
        "jersey_number": jersey_number,
        "season_team": (
            {"team": season_team[0].team, "season": season_team[1]}
            if season_team and season_team[0].id != getattr(honour, "id", None)
            else None
        ),
        "represented": (
            {
                "state": honour.team.get_state_ut_display() or honour.team.name,
                "year": honour.event.start_date.year,
                "tournament_slug": honour.event.slug,
                "team": honour.team,
            }
            if honour
            else None
        ),
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
