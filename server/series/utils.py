from server.core.models import Player, Team
from server.membership.models import Membership
from server.types import message_response

from .models import Series, SeriesRegistration, SeriesRosterInvitation


class RegistrationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


def can_register_player_to_series_roster(
    series: Series, team: Team, player: Player
) -> tuple[bool, message_response | None]:
    registered_teams_categories = SeriesRegistration.objects.filter(
        series=series, player=player
    ).values_list("team__category", flat=True)

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
    series: Series, team: Team, player: Player
) -> tuple[bool, message_response | None]:
    is_invitation_pending = SeriesRosterInvitation.objects.filter(
        series=series, team=team, to_player=player, status=SeriesRosterInvitation.Status.PENDING
    ).exists()

    if is_invitation_pending:
        return False, {"message": "This player has already been invited to your team"}

    num_registrations = SeriesRegistration.objects.filter(series=series, team=team).count()

    num_pending_invitations = SeriesRosterInvitation.objects.filter(
        series=series, team=team, status=SeriesRosterInvitation.Status.PENDING
    ).count()

    if not (num_registrations + num_pending_invitations + 1) <= series.series_roster_max_players:
        return False, {
            "message": f"You can't invite any more players. You've sent out {num_pending_invitations} invitations, there are {num_registrations} players in the roster"
        }

    return True, None


def register_player(series: Series, team: Team, player: Player) -> SeriesRegistration:
    try:
        membership = player.membership
    except Membership.DoesNotExist:
        raise RegistrationError(
            "You need an active IU membership to register for the series"
        ) from None

    if not membership.is_active:
        raise RegistrationError("You need an active IU membership to register for the series")

    if not membership.waiver_valid:
        raise RegistrationError("You need to sign the waiver first, to register for the series")

    num_registrations = SeriesRegistration.objects.filter(series=series, team=team).count()

    if not num_registrations + 1 <= series.series_roster_max_players:
        raise RegistrationError(
            f"Only {series.series_roster_max_players} can register for this series"
        )

    can_register, error = can_register_player_to_series_roster(
        series=series, team=team, player=player
    )

    if not can_register and error:
        raise RegistrationError(error["message"])

    return SeriesRegistration.objects.create(series=series, team=team, player=player)


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
