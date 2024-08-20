from server.core.models import Player, Team

from .models import Series, SeriesRegistration


class RegistrationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


def register_player(series: Series, team: Team, player: Player) -> SeriesRegistration:
    registered_teams_categories = SeriesRegistration.objects.filter(
        series=series, player=player
    ).values_list("team__category", flat=True)

    # Team has to be of the same category for school, college or state series'.
    # Allow registering with only 1 team
    if series.category in (Series.Category.SCHOOL, Series.Category.COLLEGE, Series.Category.STATE):
        if len(registered_teams_categories) != 0:
            raise RegistrationError(
                f"You can only register for 1 {series.category.lower()} team in this series"
            )
        if team.category != series.category:
            raise RegistrationError(
                f"You can only register with {series.category.lower()} teams in this series"
            )

        return SeriesRegistration.objects.create(series=series, team=team, player=player)

    # Allow any type of team to register for a club series
    if len(registered_teams_categories) == 0:
        return SeriesRegistration.objects.create(series=series, team=team, player=player)

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
        raise RegistrationError("You can register with 1 school/college team only for this series")

    if team.category in club_or_state_or_national and any(
        reg_team in club_or_state_or_national for reg_team in registered_teams_categories
    ):
        raise RegistrationError("You can register with 1 club/state/national team for this series")

    return SeriesRegistration.objects.create(series=series, team=team, player=player)
