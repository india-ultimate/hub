"""What every part of a team's tournament registration is waiting on, and why.

Pure functions over a Context built with a fixed number of queries. The
status endpoint and the checkout both call these, so what the page shows
and what checkout accepts can never disagree.
"""

import datetime
from dataclasses import asdict, dataclass, field
from typing import Any

from django.utils.timezone import now

from server.core.models import Player, Team, User
from server.registration.models import RosterEntry
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
from server.tournament.models import Event, Registration
from server.transaction.models import RazorpayTransaction
from server.utils import today as today_ist

HOLD_MINUTES = 20
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


def _open_hold(entry: RosterEntry) -> RazorpayTransaction | None:
    """The order holding this entry, unless it is paid, failed or stale."""
    order = entry.held_by_order
    if order is None or order.status in RazorpayTransaction.SETTLED or order.status == "failed":
        return None
    if order.payment_date < now() - datetime.timedelta(minutes=HOLD_MINUTES):
        return None
    return order


def build_context(
    event: Event, team: Team, viewer: User, today: datetime.date | None = None
) -> Context:
    entries = list(
        RosterEntry.objects.filter(event=event, team=team).select_related(
            "player__user", "held_by_order"
        )
    )
    paid = list(Registration.objects.filter(event=event, team=team).select_related("player__user"))
    ids = [e.player_id for e in entries] + [r.player_id for r in paid]
    ctx = Context(
        event=event,
        team=team,
        viewer=viewer,
        today=today or today_ist(),
        season=eligibility._season_of(event),
        entries=entries,
        paid=paid,
    )
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
            f"Not rostered — rostering closed {last:%b %-d}",
            Action("Request a late change", href="/tickets/new?category=Tournament"),
        )
    return None


def _not_open(ctx: Context) -> Reason | None:
    opens = ctx.event.player_registration_start_date
    if ctx.today < opens:
        return Reason(
            "timing.not_open",
            "timing",
            f"Rostering opens {opens:%b %-d} · {_days((opens - ctx.today).days)}",
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
            "Waiver not signed — only the player can sign it",
            Action("Remind", op="remind"),
        )
    scope = Scope.PLAY_CHAMPIONSHIPS if playing else Scope.STAFF_CHAMPIONSHIPS
    if message == "Subscription missing":
        if player.id in ctx.awaiting_approval:
            return Reason(
                "waiting.approval", "waiting", "Discounted subscription awaiting approval"
            )
        if ctx.season is not None and suggested_tier(player, ctx.season, scope) is None:
            # Nothing on sale they may buy, so nobody can pay for one yet.
            return Reason(
                "waiting.approval",
                "waiting",
                "Needs a discounted subscription — the player must request it",
            )
        season = ctx.season.name if ctx.season else "this season's"
        return Reason("action.subscription", "action", f"No {season} subscription")
    if message.startswith("Subscription does not cover") and ctx.season is not None:
        tier = suggested_tier(player, ctx.season, scope)
        if tier is None:
            return Reason("waiting.approval", "waiting", "Needs a tier only staff can approve")
        slug, amount = tier
        return Reason(
            "action.upgrade",
            "action",
            error["description"],
            Action(
                f"Upgrade ₹{amount // 100:,}",
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
            "Not on your series roster",
            Action("Invite to series", op="invite"),
        )
    if invite.status == InviteStatus.DECLINED:
        return Reason("waiting.declined", "waiting", "Declined the series invite")
    if invite.status == InviteStatus.EXPIRED or invite.expires_on < ctx.today:
        return Reason(
            "waiting.invite_expired",
            "waiting",
            f"Invite expired {invite.expires_on:%b %-d}",
            Action("Invite again", op="invite"),
        )
    if invite.status == InviteStatus.PENDING:
        return Reason(
            "waiting.invite",
            "waiting",
            f"Invited to series · expires {_days((invite.expires_on - ctx.today).days)}",
            Action("Resend", op="resend_invite"),
        )
    return None


def entry_reasons(ctx: Context) -> dict[int, Reason]:
    reasons: dict[int, Reason] = {
        r.player_id: Reason(
            "done.rostered",
            "done",
            "Rostered · paid",
            Action("Request change", href="/tickets/new?category=Tournament"),
        )
        for r in ctx.paid
    }
    series = ctx.event.series
    counts = {"total": 0, "F": 0, "M": 0}

    def take_spot(player: Player) -> None:
        counts["total"] += 1
        counts[player.match_up] = counts.get(player.match_up, 0) + 1

    for r in ctx.paid:
        if r.is_playing:
            take_spot(r.player)

    closed, not_open = _closed(ctx), _not_open(ctx)
    unpaid = [e for e in ctx.entries if e.player_id not in reasons]
    early: dict[int, Reason | None] = {}
    held: set[int] = set()
    for entry in unpaid:
        pid = entry.player_id
        reason = None
        if pid in ctx.elsewhere:
            reason = Reason("blocked.elsewhere", "blocked", f"Rostered for {ctx.elsewhere[pid]}")
        early[pid] = reason or _series_reason(ctx, entry) or closed
        hold = _open_hold(entry)
        if early[pid] is None and hold is not None and hold.user_id != ctx.viewer.id:
            # About to be paid for, so it holds its spot before any row is
            # checked against the caps, whatever order they were added in.
            held.add(pid)
            if _is_playing(ctx, pid):
                take_spot(entry.player)

    for entry in unpaid:
        pid, player = entry.player_id, entry.player
        playing = _is_playing(ctx, pid)
        reason = early[pid]
        if pid in held:
            reason = Reason("progress.held", "progress", "Being paid by another admin")
        if reason is None and not player.match_up:
            reason = Reason(
                "waiting.profile",
                "waiting",
                "Profile incomplete — gender matching missing",
                Action("Remind", op="remind"),
            )
        if reason is None and series is not None and playing:
            mu = player.match_up
            cap = {"F": series.event_max_players_female, "M": series.event_max_players_male}.get(mu)
            # 0 means no one, as in can_register_player_to_series_event.
            if counts["total"] + 1 > series.event_max_players_total:
                reason = Reason(
                    "limit.total",
                    "limit",
                    f"Roster full · {counts['total']}/{series.event_max_players_total}",
                )
            elif cap is not None and counts.get(mu, 0) + 1 > cap:
                label = "Female" if mu == "F" else "Male"
                reason = Reason(
                    f"limit.{'female' if mu == 'F' else 'male'}",
                    "limit",
                    f"{label}-matching limit reached ({counts.get(mu, 0)}/{cap})",
                )
        # Subscriptions after caps, so nobody is asked to pay for one to be
        # told the roster is full; before opening, so they can sort it early.
        reason = reason or _subscription_reason(ctx, entry) or not_open
        if reason is None:
            reason = Reason("ready", "ready", "Ready to pay", Action("Remove", op="remove"))
            if playing:
                take_spot(player)
        reasons[pid] = reason
    return reasons


def meter(ctx: Context, reasons: dict[int, Reason]) -> dict[str, int]:
    series = ctx.event.series
    players = {r.player_id: r.player for r in ctx.paid} | {
        e.player_id: e.player for e in ctx.entries
    }
    # Paid, ready and held rows hold a spot. A paid row says whether it
    # plays; an unpaid one goes by its series role.
    playing = {r.player_id: r.is_playing for r in ctx.paid}
    counted = [
        players[pid]
        for pid, reason in reasons.items()
        if reason.kind in ("done", "ready", "progress") and playing.get(pid, _is_playing(ctx, pid))
    ]
    return {
        "total": len(counted),
        "female_matching": sum(1 for p in counted if p.match_up == "F"),
        "male_matching": sum(1 for p in counted if p.match_up == "M"),
        "max_total": series.event_max_players_total if series else 0,
        "min_female": series.event_min_players_female if series else 0,
        "max_female": series.event_max_players_female if series else 0,
        "min_male": series.event_min_players_male if series else 0,
        "max_male": series.event_max_players_male if series else 0,
    }
