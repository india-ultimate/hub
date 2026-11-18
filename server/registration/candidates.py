"""Who a team admin might add: themselves, their series roster, past teammates, anyone."""

from dataclasses import replace
from typing import Any

from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Concat

from server.core.models import Player, Team, User
from server.duplicates.identity import full_email_match
from server.registration.state import Reason, build_context, preview
from server.series.models import Role, SeriesRegistration, is_playing_role
from server.subscription import eligibility
from server.tournament.models import Event, Registration

BROWSE_LIMIT = 20
PAGE_SIZE = 10
MIN_SEARCH = 2  # shorter text browses instead
INVITE = "Gets a series invite"
HINTS: dict[str, tuple[str | None, str | None]] = {
    # code: (text, or None for the reason's own text; button)
    "ready": ("Ready to pay", "add"),
    "ready.free": ("Ready", "add"),
    "ready.after_team_fee": (None, "add"),
    "action.subscription": ("Needs a subscription", "add"),
    "action.upgrade": ("Subscription needs an upgrade", "add"),
    "waiting.approval": ("Needs a subscription", "add"),
    "waiting.waiver": ("Waiver not signed", "add"),
    "waiting.coc": ("Code of conduct not agreed", "add"),
    "action.invite": (INVITE, "invite"),
    "waiting.invite_expired": (INVITE, "invite"),
    "waiting.declined": ("Declined before · adding re-invites", "invite"),
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
    return player.user.get_full_name() or f"player {player.pk}"


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


def _hint(reason: Reason | None) -> tuple[dict[str, Any] | None, str | None]:
    if reason is None:
        return None, None
    text, button = HINTS.get(reason.code, (None, "add"))
    return {"code": reason.code, "kind": reason.kind, "text": text or reason.text}, button


def _row(
    player: Player,
    reasons: tuple[Reason | None, Reason | None],
    history: History,
    on_list: bool,
    series_role: str | None = None,
) -> dict[str, Any]:
    """reasons: as a player, then as a coach or manager."""
    last = history.get(player.id)
    hint, button = _hint(reasons[0])
    staff_hint, staff_button = _hint(reasons[1])
    if staff_hint == hint:
        staff_hint = None
    return {
        "id": player.id,
        "name": _name(player),
        "city": player.city,
        "photo": player.profile_pic_url or None,
        "match_up": player.match_up,
        "last_event": last[1] if last else None,
        "events": len(last[2]) if last else 0,
        "on_list": on_list,
        "series_role": series_role,
        "hint": hint,
        "button": None if on_list else button,
        "staff_hint": staff_hint,
        "staff_button": None if on_list or series_role else staff_button,
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
    series_roles: dict[int, str] = {}
    if event.series_id:
        series_roles = dict(
            SeriesRegistration.objects.filter(series_id=event.series_id, team=team).values_list(
                "player_id", "role"
            )
        )
    series_ids = list(series_roles)
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
            .filter(
                Q(full_name__icontains=text)
                | (
                    Q(user__username__icontains=text)
                    if viewer.is_staff
                    else full_email_match(text, "user__username")
                )
            )
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
    adding = [players[pid] for pid in wanted if pid not in listed]

    def judged(role: str) -> dict[int, Reason]:
        reasons = preview(replace(ctx, new_role=role), adding)
        mine = reasons.get(me.id) if me is not None else None
        if me is not None and event.series is not None and mine and mine.code == "action.invite":
            # Adding oneself joins the series roster directly, so it must pass
            # what joining checks; no invite to oneself.
            error = eligibility.check(me, event.series, is_playing=is_playing_role(role))
            reasons[me.id] = (
                Reason("ready.self", "ready", "You'll join the series roster")
                if error is None
                else Reason(
                    "blocked.self_subscription",
                    "blocked",
                    (
                        "Needs a subscription"
                        if error["message"] == "Subscription missing"
                        else error["message"]
                    ),
                )
            )
        return reasons

    as_player, as_staff = judged(Role.DEFAULT), judged(Role.COACH)

    def both(pid: int) -> tuple[Reason | None, Reason | None]:
        return as_player.get(pid), as_staff.get(pid)

    return {
        "me": _row(me, both(me.id), history, False, series_roles.get(me.id)) if me else None,
        "groups": [
            {
                "key": key,
                "title": title,
                "players": [
                    _row(
                        players[pid],
                        both(pid),
                        history,
                        pid in listed,
                        series_roles.get(pid),
                    )
                    for pid in ids
                ],
            }
            for key, title, ids in groups
            if ids or key in ("matches", "others")
        ],
        "has_more": has_more,
    }
