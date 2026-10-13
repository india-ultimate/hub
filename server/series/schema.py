from datetime import date

from ninja import ModelSchema, Schema

from server.schema import (
    PlayerMinSchema,
    PlayerTinySchema,
    RegistrationCount,
    TeamMinSchema,
    UserNameSchema,
)

from .models import Series, SeriesRegistration, SeriesRosterInvitation


class SeriesSchema(ModelSchema):
    teams: list[TeamMinSchema]

    type: str

    @staticmethod
    def resolve_type(series: Series) -> str:
        return str(Series.Type._value2member_map_[series.type]._label_)  # type: ignore[attr-defined]

    category: str

    @staticmethod
    def resolve_category(series: Series) -> str:
        return str(Series.Category._value2member_map_[series.category]._label_)  # type: ignore[attr-defined]

    reg_count: list[RegistrationCount]

    @staticmethod
    def resolve_reg_count(series: Series) -> list[RegistrationCount]:
        return [
            RegistrationCount(
                team_id=team.id,
                count=SeriesRegistration.objects.filter(team=team, series=series).count(),
            )
            for team in series.teams.all()
        ]

    class Meta:
        model = Series
        fields = "__all__"


class SeriesMinSchema(ModelSchema):
    type: str
    category: str

    @staticmethod
    def resolve_type(series: Series) -> str:
        return str(Series.Type._value2member_map_[series.type]._label_)  # type: ignore[attr-defined]

    @staticmethod
    def resolve_category(series: Series) -> str:
        return str(Series.Category._value2member_map_[series.category]._label_)  # type: ignore[attr-defined]

    class Meta:
        model = Series
        fields = ["name", "slug", "start_date", "end_date"]


class TournamentSeriesSchema(ModelSchema):
    """A series as a tournament sends it: without its teams and their counts."""

    type: str
    category: str

    @staticmethod
    def resolve_type(series: Series) -> str:
        return SeriesMinSchema.resolve_type(series)

    @staticmethod
    def resolve_category(series: Series) -> str:
        return SeriesMinSchema.resolve_category(series)

    class Meta:
        model = Series
        exclude = ["teams"]


class SeriesCreateSchema(Schema):
    start_date: date
    end_date: date
    name: str
    type: str
    category: str
    series_roster_max_players: int
    event_min_players_male: int
    event_min_players_female: int
    event_max_players_male: int
    event_max_players_female: int
    player_transfer_window_start_date: date | None = None
    player_transfer_window_end_date: date | None = None
    season_id: int | None = None


class SeriesRosterInvitationCreateSchema(Schema):
    to_player_id: int
    expires_on: date | None = None
    role: str | None = None


class SeriesRosterInvitationSchema(ModelSchema):
    from_user: UserNameSchema
    to_player: PlayerTinySchema
    team: TeamMinSchema

    class Meta:
        model = SeriesRosterInvitation
        exclude = ["series"]


class AddOrRemoveTeamSeriesRegistrationSchema(Schema):
    team_slug: str


class SeriesRegistrationSchema(ModelSchema):
    team: TeamMinSchema
    player: PlayerTinySchema

    class Meta:
        model = SeriesRegistration
        fields = "__all__"


class SeriesTeamRosterSchema(ModelSchema):
    player: PlayerMinSchema

    class Meta:
        model = SeriesRegistration
        # role lets the roster page list non-playing staff apart from players.
        fields = ["player", "role"]


class SeriesRegistrationAddSchema(Schema):
    player_id: int


class SeriesRegistrationRoleSchema(Schema):
    role: str
