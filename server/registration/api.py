"""The team registration home: one team's registration for one tournament."""

import logging
from http import HTTPStatus
from typing import Any, cast

from django.conf import settings
from django.core import mail
from django.db import transaction as db_transaction
from django.http import Http404
from ninja import Router

from server.core.models import Player, Team, User
from server.registration.candidates import candidate_payload
from server.registration.models import RosterEntry, RosterSwap
from server.registration.schema import (
    AddEntrySchema,
    CheckoutOrderSchema,
    CheckoutSchema,
    SetRoleSchema,
    SwapSchema,
)
from server.registration.state import (
    HOLD_MINUTES,
    PAID_REMOVAL_REFUSED,
    build_context,
    checkout_quote,
    entry_reasons,
    is_undo,
    open_hold,
    plays,
    preview_swap,
    removal_refused,
    status_payload,
)
from server.schema import Response
from server.series.models import Role, SeriesRosterInvitation, is_playing_role
from server.series.utils import invite_to_series, register_player
from server.tournament.models import Event, Registration
from server.tournament.utils import roster_player, series_role
from server.transaction.client.razorpay import client_for, mark_transaction_completed
from server.transaction.models import AuthenticatedHttpRequest, RazorpayTransaction
from server.transaction.schema import PlayerRegistrationSchema
from server.transaction.utils import apply_transaction, create_transaction
from server.types import message_response
from server.utils import is_today_in_between_dates, today

logger = logging.getLogger(__name__)
router = Router()
Pending = SeriesRosterInvitation.Status.PENDING
Revoked = SeriesRosterInvitation.Status.REVOKED
ADMINS_ONLY: message_response = {"message": "Only team admins can change this roster"}
# The places a team admin adds people in; captains are named on the roster later.
ROSTER_ROLES = (Role.DEFAULT, Role.COACH, Role.ASSISTANT_COACH, Role.MANAGER)


def _load(event_slug: str, team_slug: str) -> tuple[Event, Team]:
    event = (
        Event.objects.filter(slug=event_slug)
        .select_related("series", "payment_account", "tournament")
        .first()
    )
    team = Team.objects.filter(slug=team_slug).first()
    if event is None or team is None or not hasattr(event, "tournament"):
        raise Http404
    return event, team


def _is_admin(team: Team, request: AuthenticatedHttpRequest) -> bool:
    return team.admins.filter(pk=request.user.pk).exists()


def _page(event: Event, team: Team) -> str:
    return f"/tournament/{event.slug}/team/{team.slug}/registration"


def _rostering_open(event: Event) -> bool:
    """Through the late window too, as the state has it."""
    return is_today_in_between_dates(
        event.player_registration_start_date, event.last_rostering_day()
    )


def _state(event: Event, team: Team, request: AuthenticatedHttpRequest, player: Player) -> Any:
    return entry_reasons(build_context(event, team, request.user))[player.id].as_dict()


@router.get("/{event_slug}/team/{team_slug}", response={200: dict[str, Any]})
def registration_status(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str
) -> dict[str, Any]:
    event, team = _load(event_slug, team_slug)
    payload = status_payload(build_context(event, team, request.user), _page(event, team))
    if payload["viewer"] is None:
        raise Http404
    return payload


@router.get(
    "/{event_slug}/team/{team_slug}/candidates",
    response={200: dict[str, Any], 403: Response, 404: Response},
)
def candidates(
    request: AuthenticatedHttpRequest,
    event_slug: str,
    team_slug: str,
    text: str = "",
    page: int = 1,
) -> tuple[int, Any]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    return 200, candidate_payload(event, team, request.user, text.strip(), page)


@router.post(
    "/{event_slug}/team/{team_slug}/roster",
    response={201: dict[str, Any], 400: Response, 403: Response},
)
def add_entry(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str, body: AddEntrySchema
) -> tuple[int, dict[str, Any] | message_response]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    player = Player.objects.filter(pk=body.player_id).select_related("user").first()
    if player is None:
        return 400, {"message": "Player does not exist"}
    if body.role is not None and body.role not in ROSTER_ROLES:
        return 400, {"message": "Pick player, coach, assistant coach or manager"}
    entry = RosterEntry.objects.filter(event=event, team=team, player=player).first()
    role = body.role or (entry.role if entry is not None else Role.DEFAULT)
    on_series = series_role(event, team, player)

    if event.series and on_series is None:
        if player.user_id == request.user.id:
            # Adding oneself: join the series roster directly, no invite to oneself.
            _, error = register_player(series=event.series, team=team, player=player, role=role)
            if error is not None:
                return 400, error
        else:
            # Invite only. An expired invite still reads as pending, and would
            # refuse "Invite again" as a second invite, so it is revoked first.
            invites = SeriesRosterInvitation.objects.filter(
                series=event.series, team=team, to_player=player, status=Pending
            )
            invites.filter(expires_on__lt=today()).update(status=Revoked)
            if not invites.exists():
                _, error = invite_to_series(
                    series=event.series,
                    team=team,
                    player=player,
                    role=role,
                    by=request.user,
                )
                if error is not None:
                    return 400, error
            elif body.role not in (None, Role.DEFAULT):
                # Picked again as staff: the invite carries the new role. A
                # plain Add leaves whatever role the invite already has.
                invites.update(role=role)
    elif not event.roster_fee(is_playing_role(on_series or role)) and (
        # Rostered at once only when the role can't change the price:
        # it's fixed, named, or every role pays the same.
        on_series
        or body.role is not None
        or event.roster_fee(True) == event.roster_fee(False)
    ):
        # Nothing to pay, so they are rostered now, in the window the row offers it.
        if not _rostering_open(event):
            return 400, {"message": "Rostering has closed, you can't roster players now !"}
        if not event.tournament.teams.filter(pk=team.pk).exists():
            return 400, {"message": f"{team.name} is not registered for {event.title}"}
        place = on_series or role
        _, error = roster_player(event, team, player, role=place, is_playing=is_playing_role(place))
        if error is not None:
            return 400, error
        RosterEntry.objects.filter(event=event, team=team, player=player).delete()
        return 201, {"player_id": player.id, "state": _state(event, team, request, player)}

    # A series member's place comes from the series roster, never the pick.
    if on_series:
        role = Role.DEFAULT
    if entry is None:
        RosterEntry.objects.create(
            event=event, team=team, player=player, role=role, added_by=request.user
        )
    elif entry.role != role and entry.held_by_order_id is None:
        entry.role = role
        entry.save(update_fields=["role"])
    return 201, {"player_id": player.id, "state": _state(event, team, request, player)}


@router.put(
    "/{event_slug}/team/{team_slug}/roster/{player_id}/role",
    response={200: dict[str, Any], 400: Response, 403: Response, 404: Response, 409: Response},
)
def set_role(
    request: AuthenticatedHttpRequest,
    event_slug: str,
    team_slug: str,
    player_id: int,
    body: SetRoleSchema,
) -> tuple[int, dict[str, Any] | message_response]:
    """The role an unpaid row will be paid for, set on the roster before paying."""
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    if body.role not in ROSTER_ROLES:
        return 400, {"message": "Pick player, coach, assistant coach or manager"}
    with db_transaction.atomic():
        # Locked as checkout locks it, so a role can't change under an order.
        # of=("self",): Postgres cannot lock the nullable side of the outer
        # join that held_by_order makes.
        entry = (
            RosterEntry.objects.select_for_update(of=("self",))
            .filter(event=event, team=team, player_id=player_id)
            .select_related("player__user", "held_by_order")
            .first()
        )
        if entry is None:
            return 404, {"message": "Not on this roster"}
        if Registration.objects.filter(event=event, team=team, player_id=player_id).exists():
            return 400, {"message": "Already on the roster"}
        if series_role(event, team, entry.player) is not None:
            return 400, {"message": "Their role is set on the series roster"}
        if open_hold(entry) is not None:
            return 409, {"message": "Being paid for. Try again in a few minutes."}
        free = not event.roster_fee(is_playing_role(body.role))
        if free and event.series is None:
            # Nothing to pay in this role, so they are rostered now, as adding does.
            if not _rostering_open(event):
                return 400, {"message": "Rostering has closed, you can't roster players now !"}
            if not event.tournament.teams.filter(pk=team.pk).exists():
                return 400, {"message": f"{team.name} is not registered for {event.title}"}
            _, error = roster_player(
                event, team, entry.player, role=body.role, is_playing=is_playing_role(body.role)
            )
            if error is not None:
                return 400, error
            entry.delete()
            return 200, {"player_id": player_id, "role": body.role}
        entry.role = body.role
        entry.save(update_fields=["role"])
        if event.series is not None:
            SeriesRosterInvitation.objects.filter(
                series=event.series, team=team, to_player_id=player_id, status=Pending
            ).update(role=body.role)
    return 200, {"player_id": player_id, "role": body.role}


@router.delete(
    "/{event_slug}/team/{team_slug}/roster/{player_id}",
    response={204: None, 403: Response, 404: Response, 409: Response},
)
def remove_entry(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str, player_id: int
) -> tuple[int, message_response | None]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    ctx = build_context(event, team, request.user)
    reason = entry_reasons(ctx).get(player_id)
    if reason is None:
        return 404, {"message": "Not on this roster"}
    rostering_open = _rostering_open(event)
    playing = plays(ctx, player_id)
    if removal_refused(event, reason, rostering_open=rostering_open, playing=playing):
        return 409, {"message": PAID_REMOVAL_REFUSED}
    undo = is_undo(event, reason, rostering_open=rostering_open, playing=playing)
    if undo:
        Registration.objects.filter(event=event, team=team, player_id=player_id).delete()
    if event.series is not None:
        SeriesRosterInvitation.objects.filter(
            series=event.series, team=team, to_player_id=player_id, status=Pending
        ).update(status=Revoked)
    RosterEntry.objects.filter(event=event, team=team, player_id=player_id).delete()
    return 204, None


@router.post(
    "/{event_slug}/team/{team_slug}/roster/{player_id}/resend-invite",
    response={200: Response, 400: Response, 403: Response, 404: Response},
)
def resend_invite(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str, player_id: int
) -> tuple[int, message_response]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    if event.series is None:
        return 400, {"message": "This tournament has no series"}
    player = Player.objects.filter(pk=player_id).first()
    if player is None:
        return 404, {"message": "Player does not exist"}
    # One live invite at a time: the old one is revoked, or the new one
    # would be refused as a second invite. The new one keeps its role.
    invites = SeriesRosterInvitation.objects.filter(
        series=event.series, team=team, to_player=player
    )
    last = invites.order_by("created_at").last()
    invites.filter(status=Pending).update(status=Revoked)
    _, error = invite_to_series(
        series=event.series,
        team=team,
        player=player,
        role=last.role if last is not None else Role.DEFAULT,
        by=request.user,
    )
    if error is not None:
        return 400, error
    return 200, {"message": "Invite sent again"}


def _tell_swapped_out(player: Player, team: Team, event: Event, by: User) -> None:
    subject = f"You've been taken off {team.name}'s roster for {event.title}"
    body = (
        f"Hi {player.user.first_name or 'there'},\n\n"
        f"{by.get_full_name() or by.username} took you off {team.name}'s roster for "
        f"{event.title} on {today():%b %-d}. Your place was passed to another player.\n\n"
        "If this is a surprise, contact your captain.\n"
    )
    try:
        mail.send_mail(subject, body, settings.EMAIL_HOST_USER, [player.user.email])
    except Exception:
        logger.exception("Couldn't email %s about a roster swap", player.user.email)


@router.post(
    "/{event_slug}/team/{team_slug}/swap",
    response={200: Response, 400: Response, 403: Response, 409: Response},
)
def swap(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str, body: SwapSchema
) -> tuple[int, message_response]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    if event.tournament.use_uc_registrations:
        return 400, {"message": "This tournament's rosters come from Ultimate Central"}
    last = event.last_rostering_day()
    if today() < event.player_registration_start_date:
        return 400, {"message": "Rostering hasn't opened yet"}
    if today() > last:
        return 400, {"message": f"Swaps ended {last:%-d %b}"}
    if body.out_player_id == body.in_player_id:
        return 400, {"message": "Pick two different players"}

    # A stale checkout for the in-player may have been paid after all, its
    # callback and webhook lost. Swapping them in too would keep both payments.
    held = (
        RosterEntry.objects.filter(
            event=event, team=team, player_id=body.in_player_id, held_by_order__isnull=False
        )
        .select_related("held_by_order")
        .first()
    )
    order = held.held_by_order if held is not None else None
    if (
        order is not None
        and order.status not in (*RazorpayTransaction.SETTLED, "failed")
        and _settle_if_paid(order)
    ):
        return 409, {"message": "Their earlier payment went through; they're rostered now"}

    with db_transaction.atomic():
        # The checkout's lock: a swap and a payment for this team never interleave.
        list(RosterEntry.objects.select_for_update().filter(event=event, team=team))
        ctx = build_context(event, team, request.user)
        out = next((r for r in ctx.paid if r.player_id == body.out_player_id), None)
        if out is None:
            return 409, {"message": "That player is no longer rostered. Refresh and try again."}
        entry = next((e for e in ctx.entries if e.player_id == body.in_player_id), None)
        if entry is None:
            return 409, {"message": "That player is no longer on the list. Refresh and try again."}
        new_name = entry.player.user.get_full_name()
        reason = preview_swap(ctx, out.player_id, entry.player_id)
        if reason.kind != "ready":
            return 409, {"message": f"{new_name} can't take the place: {reason.text}"}

        out.delete()
        role = series_role(event, team, entry.player) or entry.role
        _, error = roster_player(
            event, team, entry.player, role=role, is_playing=is_playing_role(role)
        )
        if error is not None:
            db_transaction.set_rollback(True)
            return 409, {"message": f"{new_name} can't take the place: {error['message']}"}
        entry.delete()
        # Old pages and the admin may have rostered them without clearing it.
        RosterEntry.objects.get_or_create(
            event=event,
            team=team,
            player=out.player,
            defaults={"added_by": request.user, "role": out.role},
        )
        RosterSwap.objects.create(
            event=event, team=team, out_player=out.player, in_player=entry.player, by=request.user
        )
        gone, by = out.player, request.user
        db_transaction.on_commit(lambda: _tell_swapped_out(gone, team, event, by))
    return 200, {"message": f"Swapped {gone.user.get_full_name()} for {new_name}"}


def _settle_if_paid(order: RazorpayTransaction) -> bool:
    """Whether Razorpay already took the money for this order, settling it if so.

    Its callback and webhook can both be lost, and checking out the same
    players again would charge them twice.
    """
    try:
        client = client_for(order.account)
        if client.order.fetch(order.order_id).get("status") != "paid":
            return False
        payments = client.order.payments(order.order_id).get("items", [])
    except Exception:
        logger.exception("Couldn't ask Razorpay about order %s", order.order_id)
        return False
    captured = next((p for p in payments if p.get("status") == "captured"), None)
    if captured is None:
        return False
    order.payment_id = captured["id"]
    apply_transaction(mark_transaction_completed(order))
    return True


@router.post(
    "/{event_slug}/team/{team_slug}/checkout",
    response={
        200: CheckoutOrderSchema,
        400: Response,
        401: Response,
        403: Response,
        409: dict[str, Any],
        422: Response,
        502: str,
    },
)
def checkout(
    request: AuthenticatedHttpRequest, event_slug: str, team_slug: str, body: CheckoutSchema
) -> tuple[int, Any]:
    event, team = _load(event_slug, team_slug)
    if not _is_admin(team, request):
        return 403, ADMINS_ONLY
    if not event.player_fee and not event.non_player_fee:
        return 400, {"message": "This tournament has no player fee"}
    ctx = build_context(event, team, request.user)
    reasons = entry_reasons(ctx)

    # A ready row may still be held by an earlier order: a stale one, or
    # this admin's own. Before paying for them again, ask Razorpay whether
    # that order was paid after all.
    earlier: dict[str, RazorpayTransaction] = {
        e.held_by_order.order_id: e.held_by_order
        for e in ctx.entries
        if e.held_by_order is not None
        and reasons[e.player_id].code == "ready"
        and e.held_by_order.status not in (*RazorpayTransaction.SETTLED, "failed")
    }
    paid = {pk for pk, order in earlier.items() if _settle_if_paid(order)}
    settled = [e.player_id for e in ctx.entries if e.held_by_order_id in paid]

    with db_transaction.atomic():
        # A second admin checking out waits here, then finds these players
        # held and leaves them out, so nobody is charged twice.
        list(RosterEntry.objects.select_for_update().filter(event=event, team=team))
        ctx = build_context(event, team, request.user)
        reasons = entry_reasons(ctx)
        quote = checkout_quote(ctx, reasons)
        ready = quote["ready_ids"]
        if not ready:
            if settled:
                return 400, {"message": "Their earlier payment went through; they're rostered now"}
            return 400, {"message": "No players are ready to pay for yet"}
        if set(ready) != set(body.expected_ids) or quote["amount"] != body.expected_amount:
            # The page shows who dropped out and the new total, and asks.
            gone = {
                pid: reasons[pid].text if pid in reasons else "No longer on this roster"
                for pid in body.expected_ids
                if pid not in ready
            }
            gone |= dict.fromkeys(settled, "Their earlier payment went through")
            return 409, {
                "removed": [{"player_id": pid, "reason": why} for pid, why in gone.items()],
                "old_amount": body.expected_amount,
                "new_amount": quote["amount"],
            }

        # The ordinary player-fee order: windows, eligibility, late fee and
        # the tournament's payment account are all checked again there.
        order = PlayerRegistrationSchema(event_id=event.id, team_id=team.id, player_ids=ready)
        status, data = create_transaction(request, order)
        if status != HTTPStatus.OK:
            return status, data
        RosterEntry.objects.filter(event=event, team=team, player_id__in=ready).update(
            held_by_order_id=cast(dict[str, Any], data)["order_id"]
        )
    # Razorpay stops taking payment once the players are no longer held.
    return 200, {**cast(dict[str, Any], data), "timeout": HOLD_MINUTES * 60}
