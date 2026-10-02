"""Who a team admin might add: themselves, their series roster, past teammates, anyone."""

from typing import Any

from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Concat

from server.core.models import Player, Team, User
from server.registration.state import Reason, build_context, preview
from server.series.models import SeriesRegistration
from server.subscription import eligibility
from server.tournament.models import Event, Registration

BROWSE_LIMIT = 20
PAGE_SIZE = 10
MIN_SEARCH = 2  # shorter text browses instead
INVITE = "Not on the series roster — they'll get an invite"
HINTS: dict[str, tuple[str | None, str | None]] = {
    # code: (text, or None for the reason's own text; button)
    "ready": ("Ready to pay", "add"),
    "ready.free": ("Ready", "add"),
    "ready.after_team_fee": (None, "add"),
    "action.subscription": ("Needs a subscription after adding", "add"),
    "action.upgrade": ("Needs a subscription after adding", "add"),
    "waiting.approval": ("Needs a subscription after adding", "add"),
    "waiting.waiver": ("Needs to sign the waiver", "add"),
    "action.invite": (INVITE, "invite"),
    "waiting.invite_expired": (INVITE, "invite"),
    "waiting.declined": ("Declined the series invite — adding invites them again", "invite"),
    "waiting.invite": ("Series invite pending", "add"),
    "blocked.elsewhere": (None, None),
    "blocked.series_other": (None, None),
    "timing.closed": (None, None),
    "ready.self": (None, "add"),
    "blocked.self_subscription": (None, None),
}

# player -> (latest end date, its title, keys of every other event/series)
History = dict[int, tuple[Any, str, set[str]]]


def _name(player: Player) -> str:
    return player.user.get_full_name() or player.user.email.split("@")[0]


def _history(event: Event, team: Team) -> History:
    """player -> (latest end date, its title, keys of every other event/series) for this team."""
    seen: History = {}

    def note(pid: int, end: Any, title: str, key: str) -> None:
        last, last_title, keys = seen.get(pid, (None, "", set()))
        keys.add(key)
        if last is None or end > last:
            last, last_title = end, title
        seen[pid] = (last, last_title, keys)

    for pid, end, title, eid in (
        Registration.objects.filter(team=team)
        .exclude(event=event)
        .values_list("player_id", "event__end_date", "event__title", "event_id")
    ):
        note(pid, end, title, f"e{eid}")
    other_series = SeriesRegistration.objects.filter(team=team)
    if event.series_id:
        other_series = other_series.exclude(series_id=event.series_id)
    for pid, end, title, sid in other_series.values_list(
        "player_id", "series__end_date", "series__name", "series_id"
    ):
        note(pid, end, title, f"s{sid}")
    return seen


def _row(player: Player, reason: Reason | None, history: History, on_list: bool) -> dict[str, Any]:
    last = history.get(player.id)
    text, button = (None, None) if reason is None else HINTS.get(reason.code, (None, "add"))
    return {
        "id": player.id,
        "name": _name(player),
        "city": player.city,
        "photo": player.profile_pic_url or None,
        "match_up": player.match_up,
        "last_event": last[1] if last else None,
        "events": len(last[2]) if last else 0,
        "on_list": on_list,
        "hint": None
        if reason is None
        else {"code": reason.code, "kind": reason.kind, "text": text or reason.text},
        "button": None if on_list else button,
    }


def _players(ids: list[int]) -> dict[int, Player]:
    return {p.id: p for p in Player.objects.filter(id__in=ids).select_related("user")}


def candidate_payload(
    event: Event, team: Team, viewer: User, text: str, page: int
) -> dict[str, Any]:
    listed = set(
        Registration.objects.filter(event=event, team=team).values_list("player_id", flat=True)
    ) | set(event.roster_entries.filter(team=team).values_list("player_id", flat=True))
    history = _history(event, team)
    series_ids: list[int] = []
    if event.series_id:
        series_ids = list(
            SeriesRegistration.objects.filter(series_id=event.series_id, team=team).values_list(
                "player_id", flat=True
            )
        )
    me_player = Player.objects.filter(user=viewer).select_related("user").first()
    me = me_player if me_player is not None and me_player.id not in listed else None
    hidden = listed | ({me.id} if me else set())

    groups: list[tuple[str, str, list[int]]] = []
    has_more = False
    if len(text) < MIN_SEARCH:
        players = _players(series_ids + list(history))
        if event.series is not None:
            ids = sorted(
                (pid for pid in series_ids if pid not in hidden), key=lambda i: _name(players[i])
            )[:BROWSE_LIMIT]
            groups.append(("series", f"On the {event.series.name} roster", ids))
        shown = set(series_ids)
        past = [pid for pid in history if pid not in hidden and pid not in shown]
        past.sort(key=lambda i: (-history[i][0].toordinal(), _name(players[i])))
        groups.append(("past", f"Played for {team.name} before", past[:BROWSE_LIMIT]))
    else:
        mates = set(history) | set(series_ids)
        found = (
            Player.objects.annotate(
                full_name=Concat("user__first_name", Value(" "), "user__last_name"),
                mate=Case(
                    When(id__in=mates, then=Value(1)), default=Value(0), output_field=IntegerField()
                ),
            )
            .filter(Q(full_name__icontains=text) | Q(user__username__icontains=text))
            .exclude(id__in=[me.id] if me else [])
            .order_by("-mate", "full_name", "id")
        )
        start = (max(page, 1) - 1) * PAGE_SIZE
        rows = list(found.values_list("id", "mate")[start : start + PAGE_SIZE + 1])
        has_more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        groups.append(("matches", "Your teammates", [i for i, m in rows if m]))
        groups.append(("others", "Everyone else", [i for i, m in rows if not m]))
        players = _players([i for i, _ in rows])

    wanted = [pid for _, _, ids in groups for pid in ids] + ([me.id] if me else [])
    players = players | _players([pid for pid in wanted if pid not in players])
    ctx = build_context(event, team, viewer, extra_player_ids=wanted)
    reasons = preview(ctx, [players[pid] for pid in wanted if pid not in listed])
    mine = reasons.get(me.id) if me is not None else None
    if me is not None and event.series is not None and mine and mine.code == "action.invite":
        # Adding oneself joins the series roster directly, so it must pass
        # what joining checks; no invite to oneself.
        error = eligibility.check(me, event.series, is_playing=True)
        reasons[me.id] = (
            Reason("ready.self", "ready", "You'll join the series roster")
            if error is None
            else Reason(
                "blocked.self_subscription",
                "blocked",
                f"{error['message']} — sort that out before joining the series roster",
            )
        )
    return {
        "me": _row(me, reasons.get(me.id), history, False) if me else None,
        "groups": [
            {
                "key": key,
                "title": title,
                "players": [
                    _row(players[pid], reasons.get(pid), history, pid in listed) for pid in ids
                ],
            }
            for key, title, ids in groups
            if ids or key in ("matches", "others")
        ],
        "has_more": has_more,
    }
