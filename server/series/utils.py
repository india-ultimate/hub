import jwt
from django.conf import settings
from django.core import mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from server.core.models import Player, Team, User
from server.membership import eligibility
from server.types import message_response

from .models import (
    PLAYING_ROLES,
    Role,
    Series,
    SeriesRegistration,
    SeriesRosterInvitation,
    is_playing_role,
)


class RegistrationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


def playing_registrations(series: Series, team: Team) -> int:
    """How many of a team's series roster spots are taken by players."""
    return SeriesRegistration.objects.filter(
        series=series, team=team, role__in=PLAYING_ROLES
    ).count()


def can_register_player_to_series_roster(
    series: Series,
    team: Team,
    player: Player,
    role: str = Role.DEFAULT,
    exclude_registration_id: int | None = None,
) -> tuple[bool, message_response | None]:
    """Whether this person may take a playing spot with this team.

    `exclude_registration_id` leaves one row out, for a role change: without
    it the row being edited collides with itself, and promoting a player to
    captain on their own team would be refused as a second team.
    """
    # The one-team-per-series rules are about playing for a team. Coaching or
    # managing a second team is allowed, so staff skip them.
    if not is_playing_role(role):
        return True, None

    registrations = SeriesRegistration.objects.filter(
        series=series, player=player, role__in=PLAYING_ROLES
    )
    if exclude_registration_id is not None:
        registrations = registrations.exclude(id=exclude_registration_id)
    registered_teams_categories = registrations.values_list("team__category", flat=True)

    if series.category in (Series.Category.SCHOOL, Series.Category.COLLEGE, Series.Category.STATE):
        # Player can register with only 1 team for these school, college or state series
        if len(registered_teams_categories) != 0:
            return False, {
                "message": f"You can only register for 1 {series.category.lower()} team in this series"
            }

        # Team has to be of the same category for school, college or state series'.
        if team.category != series.category:
            return False, {
                "message": f"You can only register with {series.category.lower()} teams in this series"
            }

        return True, None

    # Player can register with any type of team, for a club series
    if len(registered_teams_categories) == 0:
        return True, None

    # Allow registering with 1 club/state/school team and 1 school/college team for the club series
    # https://docs.google.com/document/d/1Ah_YUt78IKFoPsgCxawuRXAaBS8L5mbD2Lr6FkNux78
    school_or_college = (Team.CategoryTypes.SCHOOL, Team.CategoryTypes.COLLEGE)
    club_or_state_or_national = (
        Team.CategoryTypes.CLUB,
        Team.CategoryTypes.STATE,
        Team.CategoryTypes.NATIONAL,
    )

    if team.category in school_or_college and any(
        reg_team in school_or_college for reg_team in registered_teams_categories
    ):
        # Player can register with 1 school/college team only for the series
        return False, {
            "message": "You can register with 1 school/college team only for this series"
        }

    if team.category in club_or_state_or_national and any(
        reg_team in club_or_state_or_national for reg_team in registered_teams_categories
    ):
        # Player can register with 1 club/state/national team for the series"
        return False, {
            "message": "You can register with 1 club/state/national team for this series"
        }

    return True, None


def can_invite_player_to_series_roster(
    series: Series, team: Team, player: Player, role: str = Role.DEFAULT
) -> tuple[bool, message_response | None]:
    is_invitation_pending = SeriesRosterInvitation.objects.filter(
        series=series, team=team, to_player=player, status=SeriesRosterInvitation.Status.PENDING
    ).exists()

    if is_invitation_pending:
        return False, {"message": "This player has already been invited to your team"}

    # Staff take no player spot, so the roster cap doesn't apply to them.
    if not is_playing_role(role):
        return True, None

    num_registrations = playing_registrations(series, team)

    num_pending_invitations = SeriesRosterInvitation.objects.filter(
        series=series,
        team=team,
        status=SeriesRosterInvitation.Status.PENDING,
        role__in=PLAYING_ROLES,
    ).count()

    if not (num_registrations + num_pending_invitations + 1) <= series.series_roster_max_players:
        return False, {
            "message": f"You can't invite any more players. You've sent out {num_pending_invitations} invitations, there are {num_registrations} players in the roster"
        }

    return True, None


def register_player(
    series: Series, team: Team, player: Player, role: str = Role.DEFAULT
) -> tuple[SeriesRegistration, None] | tuple[None, message_response]:
    playing = is_playing_role(role)

    error = eligibility.check(player, series, is_playing=playing)
    if error is not None:
        return None, error

    if playing and not playing_registrations(series, team) + 1 <= series.series_roster_max_players:
        return None, {
            "message": f"Only {series.series_roster_max_players} players can register for this series"
        }

    can_register, error = can_register_player_to_series_roster(
        series=series, team=team, player=player, role=role
    )

    if not can_register and error:
        return None, error

    return (
        SeriesRegistration.objects.create(series=series, team=team, player=player, role=role),
        None,
    )


def change_series_role(registration: SeriesRegistration, role: str) -> message_response | None:
    """Move someone between playing and staff on a series roster."""
    if role == registration.role:
        return None

    playing = is_playing_role(role)

    error = eligibility.check(registration.player, registration.series, is_playing=playing)
    if error is not None:
        return error

    # Only a move into a playing spot takes one; this row is already counted
    # if it held one before.
    if (
        playing
        and not is_playing_role(registration.role)
        and not (
            playing_registrations(registration.series, registration.team) + 1
            <= registration.series.series_roster_max_players
        )
    ):
        return {
            "message": f"Only {registration.series.series_roster_max_players} players can register for this series"
        }

    can_register, error = can_register_player_to_series_roster(
        series=registration.series,
        team=registration.team,
        player=registration.player,
        role=role,
        exclude_registration_id=registration.id,
    )
    if not can_register and error:
        return error

    registration.role = role
    registration.save(update_fields=["role"])
    return None


def generate_invitation_token(invitation_id: int) -> str:
    mail_secret_key = settings.EMAIL_SECRET_KEY

    payload = {
        "invitation_id": invitation_id,
    }

    token = jwt.encode(payload, mail_secret_key, algorithm="HS256")
    return token


def get_details_from_invitation_token(token: str) -> tuple[bool, int | str]:
    try:
        mail_secret_key = settings.EMAIL_SECRET_KEY
        payload = jwt.decode(token, mail_secret_key, algorithms=["HS256"])

        if "invitation_id" in payload:
            return True, payload["invitation_id"]
        else:
            return False, "None"

    except jwt.InvalidTokenError:
        return False, "None"


def send_invitation_email(
    from_user: User,
    to_player: Player,
    team: Team,
    series: Series,
    accept_invitation_link: str,
    decline_invitation_link: str,
) -> None:
    subject = f"Hub | Invitation to join {team.name}'s roster"

    html_message = render_to_string(
        "series_roster_invitation_email.html",
        {
            "team_name": team.name,
            "from_name": f"{from_user.get_full_name()} ({from_user.username})",
            "series_name": series.name,
            "accept_invitation_link": accept_invitation_link,
            "decline_invitation_link": decline_invitation_link,
        },
    )
    plain_message = strip_tags(html_message)
    from_email = settings.EMAIL_HOST_USER
    to = to_player.user.email.strip().lower()

    mail.send_mail(subject, plain_message, from_email, [to], html_message=html_message)


def send_invitation_acceptation_email(
    from_user: User, to_player: Player, team: Team, series: Series
) -> None:
    subject = f"Hub | Invitation Accepted to join {team.name}'s roster"
    html_message = render_to_string(
        "series_roster_accept_email.html",
        {
            "team_name": team.name,
            "to_name": f"{to_player.user.get_full_name()} ({to_player.user.username})",
            "series_name": series.name,
        },
    )
    plain_message = strip_tags(html_message)
    from_email = settings.EMAIL_HOST_USER
    to = from_user.email.strip().lower()

    mail.send_mail(subject, plain_message, from_email, [to], html_message=html_message)


# def series_team_players_search_list(
#     series: Series, team: Team, search_text: str
# ) -> list[Player] | QuerySet[Player]:
#     # Off-season (meaning not hosted by IU) series or tournaments don't need a membership
#     # IU season/series rules don't apply
#     if series.season is not None:
#         players = (
#             Player.objects.filter(membership__is_active=True)
#             .annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
#             .filter(Q(full_name__icontains=search_text) | Q(user__username__icontains=search_text))
#             .order_by("full_name")
#         )
#         return list(
#             filter(
#                 lambda player: can_register_player_to_series_roster(
#                     series=series, team=team, player=player
#                 )[0]
#                 is True,
#                 players,
#             )
#         )

#     return (
#         Player.objects.annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
#         .filter(Q(full_name__icontains=search_text) | Q(user__username__icontains=search_text))
#         .order_by("full_name")
#     )
