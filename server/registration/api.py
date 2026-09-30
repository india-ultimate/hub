"""The team registration home: one team's registration for one tournament."""

from typing import Any

from django.http import Http404
from ninja import Router

from server.core.models import Player, Team
from server.registration.models import RosterEntry
from server.registration.schema import AddEntrySchema
from server.registration.state import build_context, entry_reasons, status_payload
from server.schema import Response
from server.series.models import Role, SeriesRosterInvitation
from server.series.utils import invite_to_series
from server.tournament.models import Event
from server.tournament.utils import roster_player, series_role
from server.transaction.models import AuthenticatedHttpRequest
from server.types import message_response
from server.utils import is_today_in_between_dates, today

router = Router()
Pending = SeriesRosterInvitation.Status.PENDING
Revoked = SeriesRosterInvitation.Status.REVOKED
ADMINS_ONLY: message_response = {"message": "Only team admins can change this roster"}


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

    if event.series and series_role(event, team, player) is None:
        # Invite only. An expired invite still reads as pending, and would
        # refuse "Invite again" as a second invite, so it is revoked first.
        invites = SeriesRosterInvitation.objects.filter(
            series=event.series, team=team, to_player=player, status=Pending
        )
        invites.filter(expires_on__lt=today()).update(status=Revoked)
        if not invites.exists():
            _, error = invite_to_series(
                series=event.series, team=team, player=player, role=Role.DEFAULT, by=request.user
            )
            if error is not None:
                return 400, error
    elif not event.player_fee:
        # Nothing to pay, so they are rostered now, in the window the row
        # offers it: through the late window too, as the state has it.
        last = max(
            filter(None, [event.player_late_penalty_end_date, event.player_registration_end_date])
        )
        if not is_today_in_between_dates(event.player_registration_start_date, last):
            return 400, {"message": "Rostering has closed, you can't roster players now !"}
        if not event.tournament.teams.filter(pk=team.pk).exists():
            return 400, {"message": f"{team.name} is not registered for {event.title}"}
        _, error = roster_player(event, team, player)
        if error is not None:
            return 400, error
        RosterEntry.objects.filter(event=event, team=team, player=player).delete()
        return 201, {"player_id": player.id, "state": _state(event, team, request, player)}

    RosterEntry.objects.get_or_create(
        event=event, team=team, player=player, defaults={"added_by": request.user}
    )
    return 201, {"player_id": player.id, "state": _state(event, team, request, player)}


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
    reason = entry_reasons(build_context(event, team, request.user)).get(player_id)
    if reason is None:
        return 404, {"message": "Not on this roster"}
    if reason.kind in ("done", "progress"):
        return 409, {"message": "Already paid, or being paid — request a change instead"}
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
    # would be refused as a second invite.
    SeriesRosterInvitation.objects.filter(
        series=event.series, team=team, to_player=player, status=Pending
    ).update(status=Revoked)
    _, error = invite_to_series(
        series=event.series, team=team, player=player, role=Role.DEFAULT, by=request.user
    )
    if error is not None:
        return 400, error
    return 200, {"message": "Invite sent again"}
