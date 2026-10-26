import datetime
from collections import Counter
from typing import Any

from django.db.models import Count, Q
from django.http import HttpRequest
from ninja import Router

from server.core.models import Player, Team
from server.schema import Response
from server.season.models import Season
from server.series.models import Role
from server.tournament.models import Match, MatchEvent, Registration, SpiritScore, Tournament
from server.types import message_response
from server.utils import full_name, today

from .schema import TeamProfileSchema

router = Router()

FORM_LENGTH = 5
LEADER_COUNT = 3
RIVAL_COUNT = 5
MIN_RIVAL_MATCHES = 2
ROLE_ORDER: list[str] = [Role.CAPTAIN, Role.SPIRIT_CAPTAIN, Role.DEFAULT]
ROLE_ORDER += [Role.COACH, Role.ASSISTANT_COACH, Role.MANAGER]
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
NO_TIME = datetime.datetime.min.replace(tzinfo=datetime.UTC)


def _player(player: Player) -> dict[str, Any]:
    return {
        "slug": player.slug,
        "full_name": full_name(player.user),
        "profile_pic_url": player.profile_pic_url,
    }


def _result(score_for: int, score_against: int) -> str:
    if score_for == score_against:
        return "D"
    return "W" if score_for > score_against else "L"


def _received(match: Match, team: Team) -> SpiritScore | None:
    return match.spirit_score_team_1 if match.team_1_id == team.id else match.spirit_score_team_2


def _tally(results: list[str]) -> dict[str, int]:
    return {"wins": results.count("W"), "losses": results.count("L"), "draws": results.count("D")}


def _leaders(team: Team, tournament_ids: list[int], matches: list[Match]) -> dict[str, Any]:
    counts: dict[str, Counter[int]] = {}
    for key, field, kind in (
        ("goals", "scored_by", MatchEvent.EventType.SCORE),
        ("assists", "assisted_by", MatchEvent.EventType.SCORE),
        ("blocks", "block_by", MatchEvent.EventType.BLOCK),
    ):
        rows = (
            MatchEvent.objects.filter(
                team=team,
                type=kind,
                stats__tournament_id__in=tournament_ids,
                **{f"{field}__isnull": False},
            )
            .values(field)
            .annotate(n=Count("id"))
        )
        counts[key] = Counter({row[field]: row["n"] for row in rows})
    for key in ("mvp", "msp"):
        counts[key] = Counter()
    for m in matches:
        score = _received(m, team)
        if score is None:
            continue
        if score.mvp_v2_id:
            counts["mvp"][score.mvp_v2_id] += 1
        if score.msp_v2_id:
            counts["msp"][score.msp_v2_id] += 1

    ids = {pid for counter in counts.values() for pid in counter}
    players = {p.id: p for p in Player.objects.filter(id__in=ids).select_related("user")}
    names = {pid: full_name(p.user).lower() for pid, p in players.items()}
    return {
        key: [
            {"player": _player(players[pid]), "value": value}
            for pid, value in sorted(counter.items(), key=lambda kv: (-kv[1], names[kv[0]]))[
                :LEADER_COUNT
            ]
        ]
        for key, counter in counts.items()
    }


def _roster(team: Team) -> dict[str, Any] | None:
    season = Season.containing(today())
    if season is None:
        return None
    registrations = list(
        Registration.objects.filter(
            team=team,
            event__tournament__isnull=False,
            event__start_date__gte=season.start_date,
            event__start_date__lte=season.end_date,
        )
        .exclude(event__tournament__status=Tournament.Status.DRAFT)
        .select_related("event", "player__user")
        .order_by("-event__start_date", "-event_id")
    )
    if not registrations:
        return None
    event = registrations[0].event
    mine = [r for r in registrations if r.event_id == event.id]
    mine.sort(key=lambda r: (ROLE_ORDER.index(r.role), full_name(r.player.user).lower()))
    return {
        "season": season.label,
        "tournament_slug": event.slug,
        "tournament_title": event.title,
        "players": [{**_player(r.player), "role": r.role} for r in mine],
    }


def build_team_profile(team: Team) -> dict[str, Any]:
    tournaments = list(
        Tournament.objects.filter(teams=team)
        .exclude(status=Tournament.Status.DRAFT)
        .select_related("event")
        .order_by("-event__start_date", "-id")
    )
    ids = [t.id for t in tournaments]
    matches = list(
        Match.objects.filter(tournament_id__in=ids, status=Match.Status.COMPLETED)
        .filter(Q(team_1=team) | Q(team_2=team))
        .filter(team_1__isnull=False, team_2__isnull=False)
        .select_related(
            "team_1",
            "team_2",
            "tournament__event",
            "spirit_score_team_1",
            "spirit_score_team_2",
        )
    )

    def side(m: Match) -> tuple[int, int, Team]:
        if m.team_1_id == team.id:
            return m.score_team_1, m.score_team_2, m.team_2  # type: ignore[return-value]
        return m.score_team_2, m.score_team_1, m.team_1  # type: ignore[return-value]

    results = [_result(*side(m)[:2]) for m in matches]
    by_tournament: dict[int, list[str]] = {}
    by_rival: dict[int, list[str]] = {}
    rival_teams: dict[int, Team] = {}
    for m, result in zip(matches, results, strict=True):
        opponent = side(m)[2]
        by_tournament.setdefault(m.tournament_id, []).append(result)
        by_rival.setdefault(opponent.id, []).append(result)
        rival_teams[opponent.id] = opponent

    received = [s.total for m in matches if (s := _received(m, team))]
    recent = sorted(
        matches, key=lambda m: (m.time is not None, m.time or NO_TIME, m.id), reverse=True
    )
    form = []
    for m in recent[:FORM_LENGTH]:
        score_for, score_against, opponent = side(m)
        event = m.tournament.event
        form.append(
            {
                "tournament_slug": event.slug,
                "tournament_title": event.title,
                "date": m.time.astimezone(IST).date() if m.time else event.start_date,
                "opponent": opponent,
                "score_for": score_for,
                "score_against": score_against,
                "result": _result(score_for, score_against),
            }
        )
    rivals = sorted(
        ((tid, rs) for tid, rs in by_rival.items() if len(rs) >= MIN_RIVAL_MATCHES),
        key=lambda item: (-len(item[1]), rival_teams[item[0]].name, item[0]),
    )[:RIVAL_COUNT]

    admins = []
    for admin in team.admins.select_related("player_profile").order_by("id"):
        player = getattr(admin, "player_profile", None)
        admins.append({"full_name": full_name(admin), "slug": player.slug if player else None})

    rows = []
    for t in tournaments:
        done = t.status == Tournament.Status.COMPLETED
        rows.append(
            {
                "slug": t.event.slug,
                "title": t.event.title,
                "start_date": t.event.start_date,
                "end_date": t.event.end_date,
                "location": t.event.location,
                "logo_light": t.logo_light.url if t.logo_light else None,
                "logo_dark": t.logo_dark.url if t.logo_dark else None,
                "status": t.status,
                "division": t.event.get_type_display(),
                "placement": (
                    next(
                        (
                            int(k)
                            for k, tid in (t.current_seeding or {}).items()
                            if tid == team.id and str(k).isdigit()
                        ),
                        None,
                    )
                    if done
                    else None
                ),
                "spirit_rank": (
                    next(
                        (
                            r.get("rank")
                            for r in t.spirit_ranking or []
                            if r.get("team_id") == team.id
                        ),
                        None,
                    )
                    if done
                    else None
                ),
                "record": _tally(by_tournament[t.id]) if t.id in by_tournament else None,
            }
        )

    return {
        "id": team.id,
        "slug": team.slug,
        "name": team.name,
        "image": team.image.url if team.image else None,
        "image_url": team.image_url,
        "category": team.category,
        "city": team.city,
        "state": team.get_state_ut_display() if team.state_ut else None,
        "admins": admins,
        "record": {"played": len(results), **_tally(results)} if results else None,
        "spirit": round(sum(received) / len(received), 1) if received else None,
        "form": form,
        "rivals": [
            {
                "team": rival_teams[tid],
                "played": len(rs),
                "wins": rs.count("W"),
                "losses": rs.count("L"),
            }
            for tid, rs in rivals
        ],
        "roster": _roster(team),
        "leaders": _leaders(team, ids, matches),
        "tournaments": rows,
    }


@router.get("/{slug}", auth=None, response={200: TeamProfileSchema, 404: Response})
def get_team_profile(
    request: HttpRequest, slug: str
) -> tuple[int, dict[str, Any]] | tuple[int, message_response]:
    team = Team.objects.filter(slug=slug).order_by("id").first()
    if team is None:
        return 404, {"message": "Team not found"}
    return 200, build_team_profile(team)
