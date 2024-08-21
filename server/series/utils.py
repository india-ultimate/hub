from django.db.models import Q, QuerySet, Value
from django.db.models.functions import Concat

from server.core.models import Player, Team
from server.types import message_response

from .models import Series, SeriesRegistration


class RegistrationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


def can_invite_player_to_series_roster(
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


def register_player(series: Series, team: Team, player: Player) -> SeriesRegistration:
    if not player.membership.is_active:
        raise RegistrationError("You need an active IU membership to register for the series")

    can_register, error = can_invite_player_to_series_roster(
        series=series, team=team, player=player
    )

    if not can_register and error:
        raise RegistrationError(error["message"])

    return SeriesRegistration.objects.create(series=series, team=team, player=player)


def series_team_players_search_list(
    series: Series, team: Team, search_text: str
) -> list[Player] | QuerySet[Player]:
    # Off-season (meaning not hosted by IU) series or tournaments don't need a membership
    # IU season/series rules don't apply
    if series.season is not None:
        players = (
            Player.objects.filter(membership__is_active=True)
            .annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
            .filter(Q(full_name__icontains=search_text) | Q(user__username__icontains=search_text))
            .order_by("full_name")
        )
        return list(
            filter(
                lambda player: can_invite_player_to_series_roster(
                    series=series, team=team, player=player
                )[0]
                is True,
                players,
            )
        )

    return (
        Player.objects.annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
        .filter(Q(full_name__icontains=search_text) | Q(user__username__icontains=search_text))
        .order_by("full_name")
    )
