from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Router

from server.core.models import Player, Team, User
from server.schema import Response, TeamSchema
from server.season.models import Season
from server.types import message_response
from server.utils import today

from .models import Series, SeriesRegistration, SeriesRosterInvitation
from .schema import (
    AddOrRemoveTeamSeriesRegistrationSchema,
    SeriesCreateSchema,
    SeriesRegistrationSchema,
    SeriesRosterInvitationCreateSchema,
    SeriesRosterInvitationSchema,
    SeriesSchema,
    SeriesTeamRosterSchema,
)
from .utils import (
    can_invite_player_to_series_roster,
    can_register_player_to_series_roster,
    register_player,
    send_invitation_email,
    get_details_from_invitation_token,
    generate_invitation_token,
)

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


@router.get("/all", auth=None, response={200: list[SeriesSchema]})
def get_all_series(request: AuthenticatedHttpRequest) -> tuple[int, QuerySet[Series]]:
    return 200, Series.objects.all()


@router.get("/", auth=None, response={200: SeriesSchema, 400: Response})
def get_series(
    request: AuthenticatedHttpRequest, id: int | None = None, slug: str | None = None
) -> tuple[int, Series | message_response]:
    if id is None and slug is None:
        return 400, {"message": "Need either id or slug to fetch series"}

    try:
        series = Series.objects.get(id=id) if id is not None else Series.objects.get(slug=slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    return 200, series


@router.post("/", response={200: SeriesSchema, 400: Response, 401: Response})
def create_series(
    request: AuthenticatedHttpRequest, series_details: SeriesCreateSchema
) -> tuple[int, Series | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create a series"}

    series = Series(
        start_date=series_details.start_date,
        end_date=series_details.end_date,
        name=series_details.name,
        type=series_details.type,
        category=series_details.category,
        series_roster_max_players=series_details.series_roster_max_players,
        event_min_players_male=series_details.event_min_players_male,
        event_min_players_female=series_details.event_min_players_female,
        event_max_players_male=series_details.event_max_players_male,
        event_max_players_female=series_details.event_max_players_female,
    )

    if series_details.player_transfer_window_start_date:
        series.player_transfer_window_start_date = series_details.player_transfer_window_start_date

    if series_details.player_transfer_window_end_date:
        series.player_transfer_window_end_date = series_details.player_transfer_window_end_date

    if series_details.season_id:
        try:
            series.season = Season.objects.get(id=series_details.season_id)
        except Season.DoesNotExist:
            return 400, {"message": "Season does not exist"}

    series.save()
    return 200, series


@router.post(
    "/{series_slug}/register-team", response={200: SeriesSchema, 400: Response, 401: Response}
)
def add_team_series_registration(
    request: AuthenticatedHttpRequest,
    series_slug: str,
    team_details: AddOrRemoveTeamSeriesRegistrationSchema,
) -> tuple[int, Series | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
        team = Team.objects.get(slug=team_details.team_slug)
    except (Series.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Series/Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can register a team to a series !"}

    # Any team can register for the Club series
    # School, College, State teams can register for the appropriate series only
    if (
        series.category != Series.Category.CLUB  # noqa: PLR1714
        and series.category != team.category
    ):
        return 400, {"message": f"Only {series.category} teams can register for this series"}
    else:
        series.teams.add(team)

    return 200, series


@router.delete(
    "/{series_slug}/deregister-team", response={200: SeriesSchema, 400: Response, 401: Response}
)
def remove_team_series_registration(
    request: AuthenticatedHttpRequest,
    series_slug: str,
    team_details: AddOrRemoveTeamSeriesRegistrationSchema,
) -> tuple[int, Series | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
        team = Team.objects.get(slug=team_details.team_slug)
    except (Series.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Series/Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can de-register from team a series !"}

    series.teams.remove(team)

    return 200, series


@router.get("/{series_slug}/team/{team_slug}", auth=None, response={200: TeamSchema, 400: Response})
def get_series_team(
    request: AuthenticatedHttpRequest, series_slug: str, team_slug: str
) -> tuple[int, Team | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if team not in series.teams.all():
        return 400, {"message": f"{team.name} is not registered for {series.name} !"}

    return 200, team


# @router.get(
#     "/{series_slug}/team/{team_slug}/players/search",
#     response={200: list[PlayerTinySchema]},
# )
# @paginate(PageNumberPagination, page_size=5)
# def search_players(
#     request: AuthenticatedHttpRequest, series_slug: str, team_slug: str, text: str = ""
# ) -> list[Player] | QuerySet[Player]:
#     try:
#         series = Series.objects.get(slug=series_slug)
#     except Series.DoesNotExist:
#         return []

#     try:
#         team = Team.objects.get(slug=team_slug)
#     except Team.DoesNotExist:
#         return []

#     return series_team_players_search_list(
#         series=series, team=team, search_text=text.strip().lower()
#     )


@router.post(
    "/{series_slug}/team/{team_slug}/invitation",
    response={200: SeriesRosterInvitationCreateSchema, 400: Response, 401: Response},
)
def send_series_invitation(
    request: AuthenticatedHttpRequest,
    series_slug: str,
    team_slug: str,
    invitation_details: SeriesRosterInvitationCreateSchema,
) -> tuple[int, SeriesRosterInvitation | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
        team = Team.objects.get(slug=team_slug)
    except (Series.DoesNotExist, Team.DoesNotExist):
        return 400, {"message": "Series does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can invite players for a series"}

    if team not in series.teams.all():
        return 400, {"message": f"{team.name} is not registered for {series.name}"}

    try:
        to_player = Player.objects.get(id=invitation_details.to_player_id)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    can_invite, error = can_invite_player_to_series_roster(
        series=series, team=team, player=to_player
    )
    if not can_invite and error:
        return 400, error

    can_register, error = can_register_player_to_series_roster(
        series=series, team=team, player=to_player
    )
    if not can_register and error:
        return 400, {"message": "Player has already registered with another team for this series"}

    invitation = SeriesRosterInvitation(
        series=series, from_user=request.user, to_player=to_player, team=team
    )

    if invitation_details.expires_on is not None:
        invitation.expires_on = invitation_details.expires_on

    invitation.save()

    invitation_token = generate_invitation_token(to_player.id, invitation.id)

    accept_invitation_link = f"{settings.EMAIL_INVITATION_BASE_URL}/accept-invitation?token={invitation_token}"
    decline_invitation_link = f"{settings.EMAIL_INVITATION_BASE_URL}/decline-invitation?token={invitation_token}"

    send_invitation_email(
        from_user=request.user, 
        to_player=to_player, 
        team=team, 
        series=series, 
        accept_invitation_link=accept_invitation_link,
        decline_invitation_link=decline_invitation_link)

    return 200, invitation


@router.delete(
    "/invitation/{invitation_id}",
    response={200: SeriesRosterInvitationSchema, 400: Response, 401: Response},
)
def revoke_series_invitation(
    request: AuthenticatedHttpRequest, invitation_id: int
) -> tuple[int, SeriesRosterInvitation | message_response]:
    try:
        invitation = SeriesRosterInvitation.objects.get(id=invitation_id)
    except SeriesRosterInvitation.DoesNotExist:
        return 400, {"messsage": "Series/Invitation does not exist"}

    if request.user != invitation.from_user:
        return 401, {
            "message": "You cannot revoke this invitation since this invitation wasn't sent by you"
        }

    if invitation.status != SeriesRosterInvitation.Status.PENDING:
        return 400, {
            "message": f"You cannot revoke an invitation that has been {invitation.status}"
        }

    invitation.status = SeriesRosterInvitation.Status.REVOKED
    invitation.save()
    return 200, invitation


@router.get(
    "/accept-invitation",
    response={200: SeriesRegistrationSchema, 400: Response},
    auth=None,
)
def accept_series_invitation_via_mail(
    request,
) -> tuple[int, SeriesRegistration | message_response]:

    token = request.GET.get("token")

    valid, invitation_id = get_details_from_invitation_token(token)

    if not valid:
        return 400, {"message": "Invalid invitation link"}

    try:
        invitation = SeriesRosterInvitation.objects.get(id=invitation_id)
    except SeriesRosterInvitation.DoesNotExist:
        return 400, {"messsage": "Invitation does not exist"}
    
    match invitation.status:
        case SeriesRosterInvitation.Status.EXPIRED:
            return 400, {"message": "This invitation has expired 😔"}

        case SeriesRosterInvitation.Status.DECLINED:
            return 400, {"message": "You cannot accept an invitation that was declined"}

        case SeriesRosterInvitation.Status.ACCEPTED:
            return 400, {
                "message": f"You already accepted this invitation on {invitation.rsvp_date}"
            }

        case SeriesRosterInvitation.Status.PENDING:
            series_registration, error = register_player(
                series=invitation.series, team=invitation.team, player=invitation.to_player
            )
            if error:
                return 400, error

            if series_registration is None:
                return 400, {"message": "Couldn't register player"}

            invitation.status = SeriesRosterInvitation.Status.ACCEPTED
            invitation.rsvp_date = today()
            invitation.save()
            return 200, series_registration

    return 400, {"message": f"'{invitation.status}' is not a valid invitation status"}


@router.get(
    "/decline-invitation",
    response={200: SeriesRosterInvitationSchema, 400: Response},
    auth=None,
)
def decline_series_invitation_via_mail(
    request,
) -> tuple[int, SeriesRosterInvitation | message_response]:

    token = request.GET.get("token")

    valid, invitation_id = get_details_from_invitation_token(token)

    if not valid:
        return 400, {"message": "Invalid invitation link"}

    try:
        invitation = SeriesRosterInvitation.objects.get(id=invitation_id)
    except SeriesRosterInvitation.DoesNotExist:
        return 400, {"messsage": "Invitation does not exist"}
    
    match invitation.status:
        case SeriesRosterInvitation.Status.EXPIRED:
            return 400, {"message": "This invitation has expired 😔"}

        case SeriesRosterInvitation.Status.ACCEPTED:
            return 400, {"message": "You cannot decline an invitation that was accepted"}

        case SeriesRosterInvitation.Status.DECLINED:
            return 400, {
                "message": f"You already declined this invitation on {invitation.rsvp_date}"
            }

        case SeriesRosterInvitation.Status.PENDING:
            invitation.status = SeriesRosterInvitation.Status.DECLINED
            invitation.rsvp_date = today()
            invitation.save()
            return 200, invitation

    return 400, {"message": f"'{invitation.status}' is not a valid invitation status"}


@router.put(
    "/invitation/{invitation_id}/accept",
    response={200: SeriesRegistrationSchema, 400: Response, 401: Response},
)
def accept_series_invitation(
    request: AuthenticatedHttpRequest, invitation_id: int
) -> tuple[int, SeriesRegistration | message_response]:
    try:
        invitation = SeriesRosterInvitation.objects.get(id=invitation_id)
    except SeriesRosterInvitation.DoesNotExist:
        return 400, {"messsage": "Invitation does not exist"}

    if request.user != invitation.to_player.user:
        return 401, {"message": "This invitation was not sent to you !"}

    match invitation.status:
        case SeriesRosterInvitation.Status.EXPIRED:
            return 400, {"message": "This invitation has expired 😔"}

        case SeriesRosterInvitation.Status.DECLINED:
            return 400, {"message": "You cannot accept an invitation that was declined"}

        case SeriesRosterInvitation.Status.ACCEPTED:
            return 400, {
                "message": f"You already accepted this invitation on {invitation.rsvp_date}"
            }

        case SeriesRosterInvitation.Status.PENDING:
            series_registration, error = register_player(
                series=invitation.series, team=invitation.team, player=invitation.to_player
            )
            if error:
                return 400, error

            if series_registration is None:
                return 400, {"message": "Couldn't register player"}

            invitation.status = SeriesRosterInvitation.Status.ACCEPTED
            invitation.rsvp_date = today()
            invitation.save()
            return 200, series_registration

    return 400, {"message": f"'{invitation.status}' is not a valid invitation status"}


@router.put(
    "/invitation/{invitation_id}/decline",
    response={200: SeriesRosterInvitationSchema, 400: Response, 401: Response},
)
def decline_series_invitation(
    request: AuthenticatedHttpRequest, invitation_id: int
) -> tuple[int, SeriesRosterInvitation | message_response]:
    try:
        invitation = SeriesRosterInvitation.objects.get(id=invitation_id)
    except SeriesRosterInvitation.DoesNotExist:
        return 400, {"messsage": "Invitation does not exist"}
    if request.user != invitation.to_player.user:
        return 401, {"message": "This invitation was not sent to you !"}

    match invitation.status:
        case SeriesRosterInvitation.Status.EXPIRED:
            return 400, {"message": "This invitation has expired 😔"}

        case SeriesRosterInvitation.Status.ACCEPTED:
            return 400, {"message": "You cannot decline an invitation that was accepted"}

        case SeriesRosterInvitation.Status.DECLINED:
            return 400, {
                "message": f"You already declined this invitation on {invitation.rsvp_date}"
            }

        case SeriesRosterInvitation.Status.PENDING:
            invitation.status = SeriesRosterInvitation.Status.DECLINED
            invitation.rsvp_date = today()
            invitation.save()
            return 200, invitation

    return 400, {"message": f"'{invitation.status}' is not a valid invitation status"}


@router.get(
    "/{series_slug}/invitations-received",
    response={200: list[SeriesRosterInvitationSchema], 400: Response},
)
def series_roster_invitations_received(
    request: AuthenticatedHttpRequest, series_slug: str
) -> tuple[int, QuerySet[SeriesRosterInvitation] | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        player = Player.objects.get(user=request.user)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    return 200, SeriesRosterInvitation.objects.filter(series=series, to_player=player)


@router.get(
    "/{series_slug}/team/{team_slug}/invitations-received",
    response={200: list[SeriesRosterInvitationSchema], 400: Response},
)
def series_team_roster_invitations_received(
    request: AuthenticatedHttpRequest, series_slug: str, team_slug: str
) -> tuple[int, QuerySet[SeriesRosterInvitation] | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    try:
        player = Player.objects.get(user=request.user)
    except Player.DoesNotExist:
        return 400, {"message": "Player does not exist"}

    return 200, SeriesRosterInvitation.objects.filter(series=series, team=team, to_player=player)


@router.get(
    "/{series_slug}/team/{team_slug}/invitations-sent",
    response={200: list[SeriesRosterInvitationSchema], 400: Response, 401: Response},
)
def series_team_roster_invitations_sent(
    request: AuthenticatedHttpRequest, series_slug: str, team_slug: str
) -> tuple[int, QuerySet[SeriesRosterInvitation] | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can see all the invitiations they've sent"}

    return 200, SeriesRosterInvitation.objects.filter(
        series=series, team=team, from_user=request.user
    )


@router.get(
    "/{series_slug}/team/{team_slug}/roster",
    auth=None,
    response={200: list[SeriesTeamRosterSchema], 400: Response},
)
def get_team_series_roster(
    request: AuthenticatedHttpRequest, series_slug: str, team_slug: str
) -> tuple[int, Any | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    return 200, SeriesRegistration.objects.filter(series=series, team=team).order_by(
        "player__user__first_name"
    )


@router.post(
    "/{series_slug}/team/{team_slug}/roster/add-self",
    response={200: SeriesRegistrationSchema, 400: Response, 401: Response},
)
def add_myself_to_team_series_roster(
    request: AuthenticatedHttpRequest,
    series_slug: str,
    team_slug: str,
) -> tuple[int, SeriesRegistration | message_response]:
    try:
        series = Series.objects.get(slug=series_slug)
    except Series.DoesNotExist:
        return 400, {"message": "Series does not exist"}

    try:
        team = Team.objects.get(slug=team_slug)
    except Team.DoesNotExist:
        return 400, {"message": "Team does not exist"}

    if request.user not in team.admins.all():
        return 401, {"message": "Only team admins can add themselves to a series roster"}

    if not hasattr(request.user, "player_profile"):
        return 400, {"message": "Player not found, please complete your registration first."}

    series_registration, error = register_player(
        series=series, team=team, player=request.user.player_profile
    )

    if error:
        return 400, error

    if series_registration is not None:
        return 200, series_registration

    return 400, {"message": "Couldn't register player"}
