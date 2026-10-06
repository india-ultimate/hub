"""What every part of a team's tournament registration is waiting on, and why.

Pure functions over a Context built with a fixed number of queries. The
status endpoint and the checkout both call these, so what the page shows
and what checkout accepts can never disagree.
"""

import datetime
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlencode

from django.utils.timezone import localdate, now

from server.core.models import Player, Team, User
from server.receipts.money import INDIA, rupees
from server.registration.models import RosterEntry, RosterSwap
from server.season.models import Season
from server.series.models import (
    PLAYING_ROLES,
    SeriesRegistration,
    SeriesRosterInvitation,
    is_playing_role,
)
from server.series.utils import playing_registrations
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.subscription import catalog, eligibility
from server.subscription.models import Scope
from server.subscription.pricing import NeedsGrant, NotForSale, quote
from server.tournament.models import Event, Registration, Tournament
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer
from server.utils import calculate_late_penalty
from server.utils import today as today_ist

HOLD_MINUTES = 20
DEADLINES = (
    "team_registration_start_date",
    "team_registration_end_date",
    "team_late_penalty_end_date",
    "player_registration_start_date",
    "player_registration_end_date",
    "player_late_penalty_end_date",
)
InviteStatus = SeriesRosterInvitation.Status


@dataclass(frozen=True)
class Action:
    label: str
    op: str | None = None
    href: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Reason:
    code: str
    kind: str
    text: str
    action: Action | None = None

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "action": self.action.as_dict() if self.action else None}


@dataclass
class Context:
    event: Event
    team: Team
    viewer: User
    today: datetime.date
    season: Season | None
    entries: list[RosterEntry]
    paid: list[Registration]
    elsewhere: dict[int, str] = field(default_factory=dict)  # player -> other team's name
    series_roles: dict[int, str] = field(
        default_factory=dict
    )  # player -> role on our series roster
    series_other: dict[int, str] = field(default_factory=dict)  # player -> other team on the series
    invites: dict[int, SeriesRosterInvitation] = field(default_factory=dict)
    awaiting_approval: set[int] = field(default_factory=set)
    series_roster_taken: int = 0  # playing registrations + pending playing invites
    team_paid: bool = False  # in event.tournament.teams


def _open_hold(entry: RosterEntry) -> RazorpayTransaction | None:
    """The order holding this entry, unless it is paid, failed or stale."""
    order = entry.held_by_order
    if order is None or order.status in RazorpayTransaction.SETTLED or order.status == "failed":
        return None
    if order.payment_date < now() - datetime.timedelta(minutes=HOLD_MINUTES):
        return None
    return order


def build_context(
    event: Event,
    team: Team,
    viewer: User,
    today: datetime.date | None = None,
    extra_player_ids: Iterable[int] = (),
) -> Context:
    entries = list(
        RosterEntry.objects.filter(event=event, team=team).select_related(
            "player__user", "held_by_order"
        )
    )
    paid = list(
        Registration.objects.filter(event=event, team=team)
        .select_related("player__user")
        .order_by("pk")
    )
    ids = [e.player_id for e in entries] + [r.player_id for r in paid] + list(extra_player_ids)
    ctx = Context(
        event=event,
        team=team,
        viewer=viewer,
        today=today or today_ist(),
        season=eligibility._season_of(event),
        entries=entries,
        paid=paid,
    )
    ctx.team_paid = Tournament.objects.filter(event=event, teams=team).exists()
    ctx.elsewhere = dict(
        Registration.objects.filter(event=event, player_id__in=ids)
        .exclude(team=team)
        .values_list("player_id", "team__name")
    )
    if (series := event.series) is not None:
        for player_id, team_id, team_name, role in SeriesRegistration.objects.filter(
            series=series, player_id__in=ids
        ).values_list("player_id", "team_id", "team__name", "role"):
            if team_id == team.id:
                ctx.series_roles[player_id] = role
            else:
                ctx.series_other[player_id] = team_name
        for invite in SeriesRosterInvitation.objects.filter(
            series=series, team=team, to_player_id__in=ids
        ).order_by("created_at"):
            ctx.invites[invite.to_player_id] = invite  # latest wins
        # The same count can_invite_player_to_series_roster refuses an invite on.
        ctx.series_roster_taken = (
            playing_registrations(series, team)
            + SeriesRosterInvitation.objects.filter(
                series=series,
                team=team,
                status=InviteStatus.PENDING,
                role__in=PLAYING_ROLES,
            ).count()
        )
    if ctx.season is not None:
        ctx.awaiting_approval = set(
            ServiceRequest.objects.filter(
                type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
                status=ServiceRequestStatus.PENDING,
                season=ctx.season,
                service_players__in=ids,
            ).values_list("service_players", flat=True)
        )
    return ctx


def suggested_tier(player: Player, season: Season, scope: str) -> tuple[str, int] | None:
    """The cheapest plan this person could be bought that covers the scope."""
    for plan in sorted(catalog.plans_for(season), key=lambda p: p.amount):
        if not plan.type.allows(scope):
            continue
        try:
            priced = quote(player, plan)
        except (NotForSale, NeedsGrant):
            continue
        return plan.type.slug, priced.amount
    return None


def _days(n: int) -> str:
    return "today" if n <= 0 else f"in {n} day{'s' if n != 1 else ''}"


def _is_playing(ctx: Context, player_id: int) -> bool:
    if ctx.event.series_id:
        return is_playing_role(ctx.series_roles.get(player_id, "DFLT"))
    return True


def _closed(ctx: Context) -> Reason | None:
    e = ctx.event
    last = max(filter(None, [e.player_late_penalty_end_date, e.player_registration_end_date]))
    if ctx.today > last:
        return Reason(
            "timing.closed",
            "timing",
            f"Rostering closed {last:%-d %b}",
            Action("Request a late change", href="/tickets/new?category=Tournament"),
        )
    return None


def _not_open(ctx: Context) -> Reason | None:
    opens = ctx.event.player_registration_start_date
    if ctx.today < opens:
        return Reason(
            "timing.not_open",
            "timing",
            f"Rostering opens {opens:%-d %b}",
        )
    return None


def _subscription_reason(ctx: Context, entry: RosterEntry) -> Reason | None:
    player = entry.player
    playing = _is_playing(ctx, player.id)
    error = eligibility.check(player, ctx.event, is_playing=playing)
    if error is None:
        return None
    message = error["message"]
    if message == "Waiver not signed":
        return Reason(
            "waiting.waiver",
            "waiting",
            "Waiver not signed",
            Action("Remind", op="remind"),
        )
    if message == "Code of conduct not agreed":
        return Reason(
            "waiting.coc", "waiting", "Code of conduct not agreed", Action("Remind", op="remind")
        )
    scope = Scope.PLAY_CHAMPIONSHIPS if playing else Scope.STAFF_CHAMPIONSHIPS
    if message == "Subscription missing":
        if player.id in ctx.awaiting_approval:
            return Reason("waiting.approval", "waiting", "Subscription awaiting approval")
        if ctx.season is not None and suggested_tier(player, ctx.season, scope) is None:
            # Nothing on sale they may buy, so nobody can pay for one yet.
            return Reason(
                "waiting.approval",
                "waiting",
                "Needs a discounted subscription",
            )
        return Reason("action.subscription", "action", "No subscription")
    if message.startswith("Subscription does not cover") and ctx.season is not None:
        tier = suggested_tier(player, ctx.season, scope)
        if tier is None:
            return Reason("waiting.approval", "waiting", "Waiting on staff approval")
        slug, amount = tier
        return Reason(
            "action.upgrade",
            "action",
            error["description"],
            Action(
                f"Upgrade {rupees(amount)}",
                href=f"/subscription/{player.id}?tab=individual&tier={slug}&return=__RETURN__",
            ),
        )
    return Reason("blocked.other", "blocked", message)


def _series_reason(ctx: Context, entry: RosterEntry) -> Reason | None:
    pid = entry.player_id
    if not ctx.event.series_id or pid in ctx.series_roles:
        return None
    if pid in ctx.series_other:
        return Reason(
            "blocked.series_other", "blocked", f"On {ctx.series_other[pid]}'s series roster"
        )
    invite = ctx.invites.get(pid)
    series = ctx.event.series
    # The rows below that offer to (re)invite.
    invitable = (
        invite is None
        or invite.status in (InviteStatus.REVOKED, InviteStatus.EXPIRED, InviteStatus.ACCEPTED)
        or (invite.status == InviteStatus.PENDING and invite.expires_on < ctx.today)
    )
    if invitable and series and ctx.series_roster_taken >= series.series_roster_max_players:
        return Reason(
            "limit.series_roster",
            "limit",
            f"Series roster full · {ctx.series_roster_taken}/{series.series_roster_max_players}",
        )
    # Accepted, yet not on the series roster: taken off it since.
    if invite is None or invite.status in (InviteStatus.REVOKED, InviteStatus.ACCEPTED):
        return Reason(
            "action.invite",
            "action",
            "Not on series roster",
            Action("Invite", op="invite"),
        )
    if invite.status == InviteStatus.DECLINED:
        return Reason("waiting.declined", "waiting", "Declined the invite")
    if invite.status == InviteStatus.EXPIRED or invite.expires_on < ctx.today:
        return Reason(
            "waiting.invite_expired",
            "waiting",
            f"Invite expired {invite.expires_on:%-d %b}",
            Action("Invite again", op="invite"),
        )
    if invite.status == InviteStatus.PENDING:
        return Reason(
            "waiting.invite",
            "waiting",
            f"Invite sent · expires {_days((invite.expires_on - ctx.today).days)}",
            Action("Resend", op="resend_invite"),
        )
    return None


def _take(counts: dict[str, int], player: Player) -> None:
    counts["total"] += 1
    counts[player.match_up] = counts.get(player.match_up, 0) + 1


def _paid_counts(ctx: Context, exclude: int | None = None) -> dict[str, int]:
    counts = {"total": 0, "F": 0, "M": 0}
    for r in ctx.paid:
        if r.is_playing and r.player_id != exclude:
            _take(counts, r.player)
    return counts


def _early_reason(ctx: Context, entry: RosterEntry) -> Reason | None:
    """What blocks a row before any spot is counted."""
    pid = entry.player_id
    if pid in ctx.elsewhere:
        return Reason("blocked.elsewhere", "blocked", f"Rostered for {ctx.elsewhere[pid]}")
    return _series_reason(ctx, entry) or _closed(ctx)


def _cap_reason(
    ctx: Context, player: Player, counts: dict[str, int], *, total: bool = True
) -> Reason | None:
    series = ctx.event.series
    if series is None or not _is_playing(ctx, player.id):
        return None
    mu = player.match_up
    cap = {"F": series.event_max_players_female, "M": series.event_max_players_male}.get(mu)
    # 0 means no one, as in can_register_player_to_series_event.
    if total and counts["total"] + 1 > series.event_max_players_total:
        return Reason(
            "limit.total",
            "limit",
            "Roster full",
        )
    if cap is not None and counts.get(mu, 0) + 1 > cap:
        label = "Female" if mu == "F" else "Male"
        return Reason(
            f"limit.{'female' if mu == 'F' else 'male'}",
            "limit",
            f"{label}-matching limit reached",
        )
    return None


def _ready_reason(ctx: Context) -> Reason:
    if not ctx.team_paid:
        text = (
            "Ready once the team fee is paid"
            if ctx.event.team_fee
            else "Ready once the team is registered"
        )
        return Reason("ready.after_team_fee", "waiting", text)
    if ctx.event.player_fee:
        return Reason("ready", "ready", "Ready to pay")
    # Nothing to pay, so it is rostered straight away, not checked out.
    return Reason("ready.free", "ready", "Accepted", Action("Add", op="roster"))


def _unpaid_reason(
    ctx: Context,
    entry: RosterEntry,
    counts: dict[str, int],
    early: Reason | None,
    *,
    total: bool = True,
) -> Reason:
    """One unpaid row, after the early checks. Takes a spot in counts when ready."""
    player = entry.player
    reason = early
    if reason is None and not player.match_up:
        reason = Reason(
            "waiting.profile",
            "waiting",
            "Profile missing gender matching",
            Action("Remind", op="remind"),
        )
    if reason is None:
        reason = _cap_reason(ctx, player, counts, total=total)
    # Subscriptions after caps, so nobody is asked to pay for one to be
    # told the roster is full; before opening, so they can sort it early.
    reason = reason or _subscription_reason(ctx, entry) or _not_open(ctx)
    if reason is None:
        reason = _ready_reason(ctx)
        if _is_playing(ctx, player.id):
            _take(counts, player)
    return reason


def _evaluate(ctx: Context) -> tuple[dict[int, Reason], dict[str, int]]:
    reasons: dict[int, Reason] = {
        r.player_id: Reason("done.rostered", "done", "Rostered · paid") for r in ctx.paid
    }
    counts = _paid_counts(ctx)
    unpaid = [e for e in ctx.entries if e.player_id not in reasons]
    early = {e.player_id: _early_reason(ctx, e) for e in unpaid}
    held: set[int] = set()
    for entry in unpaid:
        pid = entry.player_id
        hold = _open_hold(entry)
        if early[pid] is None and hold is not None and hold.user_id != ctx.viewer.id:
            # About to be paid for, so it holds its spot before any row is
            # checked against the caps, whatever order they were added in.
            held.add(pid)
            if _is_playing(ctx, pid):
                _take(counts, entry.player)
    for entry in unpaid:
        pid = entry.player_id
        if pid in held:
            reasons[pid] = Reason("progress.held", "progress", "Being paid by another admin")
        else:
            reasons[pid] = _unpaid_reason(ctx, entry, counts, early[pid])
    return reasons, counts


def entry_reasons(ctx: Context) -> dict[int, Reason]:
    return _evaluate(ctx)[0]


def preview(ctx: Context, players: Iterable[Player]) -> dict[int, Reason]:
    """What each person would show if added now. Build ctx with their ids."""
    reasons, counts = _evaluate(ctx)
    out: dict[int, Reason] = {}
    for player in players:
        if player.id in reasons:
            continue
        entry = RosterEntry(event=ctx.event, team=ctx.team, player=player)
        out[player.id] = _unpaid_reason(ctx, entry, dict(counts), _early_reason(ctx, entry))
    return out


def _swap_in_reason(
    ctx: Context, entry: RosterEntry, out_player_id: int | None = None, *, total: bool = False
) -> Reason:
    """Whether this unpaid row could take a paid place, with out's gone."""
    early = _early_reason(ctx, entry)
    if early is not None:
        return early
    if _open_hold(entry) is not None:
        return Reason("progress.held", "progress", "Being paid for. Try again in a few minutes.")
    counts = _paid_counts(ctx, exclude=out_player_id)
    for other in ctx.entries:
        hold = _open_hold(other)
        if other is not entry and hold is not None and _is_playing(ctx, other.player_id):
            _take(counts, other.player)
    return _unpaid_reason(ctx, entry, counts, None, total=total)


def preview_swap(ctx: Context, out_player_id: int, in_player_id: int) -> Reason:
    """Whether in can take out's paid place: judged with out already gone."""
    out = next(r for r in ctx.paid if r.player_id == out_player_id)
    entry = next(e for e in ctx.entries if e.player_id == in_player_id)
    # Same size roster, so only the gender caps apply, unless a player
    # takes a staff member's place and the playing count grows.
    grows = not out.is_playing and _is_playing(ctx, in_player_id)
    reason = _swap_in_reason(ctx, entry, out_player_id, total=grows)
    series = ctx.event.series
    if reason.kind != "ready" or series is None or not out.is_playing:
        return reason
    mu = out.player.match_up
    if mu == entry.player.match_up and _is_playing(ctx, entry.player_id):
        return reason  # same count of out's gender afterwards
    minimum = {"F": series.event_min_players_female, "M": series.event_min_players_male}.get(mu, 0)
    before = _paid_counts(ctx).get(mu, 0)
    if before >= minimum > before - 1:
        label = "female" if mu == "F" else "male"
        return Reason(
            "limit.minimum",
            "limit",
            f"Would leave too few {label}-matching",
        )
    return reason


def _best_swap_state(ctx: Context, entry: RosterEntry) -> Reason:
    """Swap state for an unpaid row: ready if swapping out any paid player
    works. Tries the likeliest out-players first -- like for like (a player
    of the same gender, or staff for staff) -- and stops at any reason that
    isn't a limit, as only limits depend on who goes out."""
    playing, mu = _is_playing(ctx, entry.player_id), entry.player.match_up

    def rank(r: Registration) -> int:
        if not r.is_playing:
            return 1 if playing else 0
        return 0 if playing and r.player.match_up == mu else 2

    # preview_swap sees the out-player only through these two fields, so one
    # try per pair gives the same answer as trying everyone, in <= 4 tries.
    outs: dict[tuple[bool, str], Registration] = {}
    for r in sorted(ctx.paid, key=rank):
        outs.setdefault((r.is_playing, r.player.match_up), r)
    first: Reason | None = None
    for out in outs.values():
        reason = preview_swap(ctx, out.player_id, entry.player_id)
        if reason.kind != "limit":
            return reason
        first = first or reason
    return first or _swap_in_reason(ctx, entry)  # nobody paid; the dialog can't open


def meter(ctx: Context, reasons: dict[int, Reason]) -> dict[str, int]:
    series = ctx.event.series
    players = {r.player_id: r.player for r in ctx.paid} | {
        e.player_id: e.player for e in ctx.entries
    }
    # Paid, ready and held rows hold a spot, as do ready rows waiting on
    # the team fee. A paid row says whether it plays; an unpaid one goes
    # by its series role.
    playing = {r.player_id: r.is_playing for r in ctx.paid}
    counted = [
        players[pid]
        for pid, reason in reasons.items()
        if (reason.kind in ("done", "ready", "progress") or reason.code == "ready.after_team_fee")
        and playing.get(pid, _is_playing(ctx, pid))
    ]
    return {
        "total": len(counted),
        "female_matching": sum(1 for p in counted if p.match_up == "F"),
        "male_matching": sum(1 for p in counted if p.match_up == "M"),
        "max_total": series.event_max_players_total if series else 0,
        "min_total": series.event_min_players_total if series else 0,
        "min_female": series.event_min_players_female if series else 0,
        "max_female": series.event_max_players_female if series else 0,
        "min_male": series.event_min_players_male if series else 0,
        "max_male": series.event_max_players_male if series else 0,
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _payments_blocked(event: Event) -> dict[str, Any] | None:
    """The callout in place of any pay button while the account can't take orders."""
    account = event.payment_account
    if account is None or account.is_ready():
        return None
    text = "Payments aren't open yet"
    ask = Action("Ask organisers", href="/tickets/new?category=Tournament").as_dict()
    return {"kind": "blocked", "text": text, "action": ask}


def _team_fee_step(ctx: Context) -> dict[str, Any]:
    e, team = ctx.event, ctx.team
    tournament = e.tournament
    step: dict[str, Any] = {
        "key": "team_fee",
        "title": "Team fee",
        "detail": "",
        "state": "current",
        "callout": None,
    }
    ask = Action("Ask organisers", href="/tickets/new?category=Tournament").as_dict()
    if tournament.teams.filter(pk=team.pk).exists():
        if not e.team_fee:
            return {**step, "state": "done", "title": "Team registered"}
        return {**step, "state": "done", "title": "Team fee paid"}
    if e.series is not None and not e.series.teams.filter(pk=team.pk).exists():
        text = f"Register for {e.series.name} first"
        return {
            **step,
            "state": "locked",
            "callout": {"kind": "waiting", "text": text, "action": None},
        }
    refunded = (
        RazorpayTransaction.objects.filter(
            event=e,
            team=team,
            type__in=[
                RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
                RazorpayTransaction.TransactionTypeChoices.PARTIAL_TEAM_REGISTRATION,
            ],
            status=RazorpayTransaction.TransactionStatusChoices.REFUNDED,
        )
        .values_list("amount", flat=True)
        .first()
    )
    if refunded is not None and not tournament.partial_teams.filter(pk=team.pk).exists():
        step["detail"] = f"Withdrawn · refunded {rupees(refunded)}"
    opens = e.team_registration_start_date
    last = max(filter(None, [e.team_late_penalty_end_date, e.team_registration_end_date]))
    if step["detail"] and not opens <= ctx.today <= last:
        # Withdrawn, and it can't pay again now.
        withdrawn = {"kind": "timing", "text": step["detail"], "action": None}
        return {**step, "state": "locked", "callout": withdrawn}
    if ctx.today < opens:
        text = f"Opens {opens:%-d %b}"
        return {
            **step,
            "state": "locked",
            "callout": {"kind": "timing", "text": text, "action": None},
        }
    if ctx.today > last:
        late = Action("Request late entry", href="/tickets/new?category=Tournament").as_dict()
        text = f"Closed {last:%-d %b}"
        return {
            **step,
            "state": "locked",
            "callout": {"kind": "timing", "text": text, "action": late},
        }
    registered = tournament.teams.count()
    if e.max_num_teams and registered >= e.max_num_teams:
        text = f"Full ({e.max_num_teams} teams)"
        return {
            **step,
            "state": "locked",
            "callout": {"kind": "limit", "text": text, "action": ask},
        }
    if not e.team_fee:
        free = Action("Register", op="register_free").as_dict()
        text = "Free entry"
        return {**step, "callout": {"kind": "timing", "text": text, "action": free}}
    # The late fee goes on the full fee or on the rest, never on a partial,
    # as create_transaction charges it.
    days_late, penalty = calculate_late_penalty(
        e.team_registration_end_date, e.team_late_penalty, e.team_late_penalty_end_date
    )
    by_day = f" + {_plural(days_late, 'day')} × {rupees(e.team_late_penalty)}"  # noqa: RUF001
    if tournament.partial_teams.filter(pk=team.pk).exists():
        rest = e.team_fee - e.partial_team_fee
        paid = rupees(e.partial_team_fee)
        owed = f"{rupees(rest)}{by_day}" if penalty else f"{rupees(rest)} left"
        pay = Action(f"Pay {rupees(rest + penalty)}", op="pay_team_rest").as_dict()
        text = f"{rupees(rest + penalty)} left"
        return {
            **step,
            "detail": f"{paid} paid · {owed}",
            "callout": _payments_blocked(e) or {"kind": "timing", "text": text, "action": pay},
        }
    total = e.team_fee + penalty
    detail = f"{rupees(e.team_fee)}{by_day}" if penalty else ""
    pay = Action(f"Pay {rupees(total)}", op="pay_team").as_dict()
    callout: dict[str, Any] = {
        "kind": "timing",
        "text": rupees(total),
        "action": pay,
    }
    partial_end = e.team_partial_registration_end_date or e.team_registration_end_date
    if e.partial_team_fee and ctx.today <= partial_end:
        # The one callout with a second button: part now, the rest later.
        label = f"Pay {rupees(e.partial_team_fee)}"
        callout["text"] = f"{rupees(total)}, or {rupees(e.partial_team_fee)} now and the rest later"
        callout["secondary_action"] = Action(label, op="pay_team_partial").as_dict()
    callout = _payments_blocked(e) or callout
    return {**step, "detail": detail or step["detail"], "callout": callout}


def checkout_quote(ctx: Context, reasons: dict[int, Reason]) -> dict[str, Any]:
    """Who paying now would cover, and what it would cost. Checkout agrees."""
    e = ctx.event
    ready = [pid for pid, r in reasons.items() if r.code == "ready"]
    _, penalty = calculate_late_penalty(
        e.player_registration_end_date, e.player_late_penalty, e.player_late_penalty_end_date
    )
    return {
        "ready_ids": ready,
        "per_player": e.player_fee,
        "penalty_per_player": penalty,
        "penalty_from": e.player_registration_end_date.isoformat(),
        "amount": (e.player_fee + penalty) * len(ready),
        # Named only when it isn't India Ultimate: no account means ours.
        "payee_name": e.payment_account.name if e.payment_account else None,
        "held_by_other_admin_ids": [pid for pid, r in reasons.items() if r.code == "progress.held"],
    }


def _handoff(ctx: Context, reasons: dict[int, Reason], page_path: str) -> dict[str, Any] | None:
    """The step callout that sends the admin to buy the missing subscriptions."""
    need = [pid for pid, r in reasons.items() if r.code == "action.subscription"]
    if not need or ctx.season is None:
        return None
    players = {e.player_id: e.player for e in ctx.entries}
    tiers = []
    for pid in need:
        scope = Scope.PLAY_CHAMPIONSHIPS if _is_playing(ctx, pid) else Scope.STAFF_CHAMPIONSHIPS
        if tier := suggested_tier(players[pid], ctx.season, scope):
            tiers.append((pid, tier))
    if not tiers:
        return None
    total = sum(amount for _, (_, amount) in tiers)
    query = urlencode(
        {
            "players": ",".join(str(pid) for pid, _ in tiers),
            "tiers": ",".join(f"{pid}:{slug}" for pid, (slug, _) in tiers),
            "return": page_path,
        },
        safe=",:/",
    )
    n = len(tiers)
    need_s = "needs" if n == 1 else "need"
    return {
        "kind": "action",
        "text": f"{_plural(n, 'player')} {need_s} a subscription",
        "action": Action(
            f"Pay {rupees(total)}",
            href=f"/subscription/group?{query}",
        ).as_dict(),
    }


def step_states(ctx: Context, reasons: dict[int, Reason], page_path: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    series = ctx.event.series
    if series is not None:
        in_series = series.teams.filter(pk=ctx.team.pk).exists()
        step: dict[str, Any] = {
            "key": "series",
            "title": f"In {series.name}",
            "detail": "",
            "state": "done",
            "callout": None,
        }
        if not in_series and series.end_date < ctx.today:
            ask = Action("Ask organisers", href="/tickets/new?category=Tournament").as_dict()
            text = f"Series registration closed {series.end_date:%-d %b}"
            step |= {
                "title": f"Join {series.name}",
                "state": "locked",
                "callout": {"kind": "timing", "text": text, "action": ask},
            }
        elif not in_series:
            join = Action(f"Register for {series.name}", op="register_series").as_dict()
            text = f"Register for {series.name}"
            step |= {
                "title": f"Join {series.name}",
                "state": "current",
                "callout": {"kind": "action", "text": text, "action": join},
            }
        steps.append(step)
    fee = _team_fee_step(ctx)
    steps.append(fee)
    ready = [pid for pid, r in reasons.items() if r.code == "ready"]
    # Ready rows waiting on the team fee aren't waiting on the player.
    waiting = sum(
        1 for r in reasons.values() if r.kind == "waiting" and r.code != "ready.after_team_fee"
    )
    callout = _handoff(ctx, reasons, page_path)
    if callout is None and not ready and waiting:
        text = f"Waiting on {_plural(waiting, 'player')}"
        callout = {"kind": "waiting", "text": text, "action": None}
    callout = _payments_blocked(ctx.event) or callout
    roster_done = bool(reasons) and all(r.kind == "done" for r in reasons.values())
    roster_state = "done" if roster_done else "current"
    done_title = "Roster paid" if ctx.event.player_fee else "Roster done"
    steps.append(
        {
            "key": "roster",
            "title": done_title if roster_state == "done" else "Roster",
            "detail": "",
            "state": roster_state if fee["state"] == "done" else "locked",
            "callout": callout,
        }
    )
    return steps


def viewer_role(ctx: Context) -> str | None:
    """admin > member > staff; None means the page doesn't exist for them."""
    user, event, team = ctx.viewer, ctx.event, ctx.team
    if team.admins.filter(pk=user.pk).exists():
        return "admin"
    member = Registration.objects.filter(event=event, team=team, player__user=user).exists() or (
        event.series_id is not None
        and SeriesRegistration.objects.filter(
            series_id=event.series_id, team=team, player__user=user
        ).exists()
    )
    if member:
        return "member"
    if user.is_staff:
        return "staff"
    return None


def all_set(steps: list[dict[str, Any]], m: dict[str, int]) -> bool:
    """Team fee and roster done, and the series' minimums met."""
    done = {s["key"] for s in steps if s["state"] == "done"}
    return (
        {"team_fee", "roster"} <= done
        and m["total"] >= m["min_total"]
        and m["female_matching"] >= m["min_female"]
        and m["male_matching"] >= m["min_male"]
    )


def status_payload(ctx: Context, page_path: str) -> dict[str, Any]:
    """Everything the team registration page renders, in one body."""
    reasons = entry_reasons(ctx)
    players = {r.player_id: r.player for r in ctx.paid} | {
        e.player_id: e.player for e in ctx.entries
    }
    e = ctx.event
    rostered = [r.player_id for r in ctx.paid]
    paid_on: dict[int, str] = {}
    for pid, when in (
        RazorpayTransactionPlayer.objects.filter(
            player_id__in=rostered,
            refunds__isnull=True,
            transaction__event=e,
            transaction__team=ctx.team,
            transaction__type=RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION,
            transaction__status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        .order_by("transaction__payment_date")
        .values_list("player_id", "transaction__payment_date")
    ):
        paid_on[pid] = localdate(when, INDIA).isoformat()  # the latest wins
    swapped_for: dict[int, dict[str, str]] = {}
    swaps = RosterSwap.objects.filter(event=e, team=ctx.team, in_player_id__in=rostered)
    for s in swaps.select_related("out_player__user"):  # newest first
        swapped_for.setdefault(
            s.in_player_id,
            {"name": s.out_player.user.get_full_name(), "on": localdate(s.at, INDIA).isoformat()},
        )

    # What the swap dialog offers each unpaid row: past a full roster,
    # which a swap doesn't grow, to whatever else stands in the way.
    swap_states = {
        e.player_id: _best_swap_state(ctx, e)
        for e in ctx.entries
        if reasons[e.player_id].kind != "done"
    }

    def row(pid: int) -> dict[str, Any]:
        p = players[pid]
        swap = swap_states.get(pid)
        state = reasons[pid].as_dict()
        if state["action"] and state["action"]["href"]:
            state["action"]["href"] = state["action"]["href"].replace("__RETURN__", page_path)
        return {
            "player": {
                "id": p.id,
                "name": p.user.get_full_name(),
                "iu_id": p.iu_id,
                "city": p.city,
                "match_up": p.match_up,
                "photo": p.profile_pic_url or None,
            },
            "role": ctx.series_roles.get(pid, "DFLT"),
            "state": state,
            "paid_on": paid_on.get(pid),
            "swapped_for": swapped_for.get(pid),
            "swap_state": swap and {"code": swap.code, "kind": swap.kind, "text": swap.text},
        }

    steps = step_states(ctx, reasons, page_path)
    m = meter(ctx, reasons)
    return {
        "team": {"id": ctx.team.id, "name": ctx.team.name, "slug": ctx.team.slug},
        "event": {
            "id": e.id,
            "title": e.title,
            "slug": e.slug,
            "start_date": e.start_date.isoformat(),
            "end_date": e.end_date.isoformat(),
            "location": e.location,
            "series": e.series.name if e.series else None,
            # The page's deadline chips.
            **{name: d.isoformat() if (d := getattr(e, name)) else None for name in DEADLINES},
            "team_late_penalty": e.team_late_penalty,  # per day, paise
            "player_late_penalty": e.player_late_penalty,
        },
        "viewer": viewer_role(ctx),
        "steps": steps,
        "all_set": all_set(steps, m),
        "roster": {"entries": [row(pid) for pid in reasons], "meter": m},
        "checkout": checkout_quote(ctx, reasons),
    }
