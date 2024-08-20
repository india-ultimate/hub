from datetime import date

from ninja import ModelSchema, Schema

from server.schema import PlayerMinSchema, PlayerTinySchema, TeamMinSchema, UserMinSchema
from server.season.models import Season

from .models import Series, SeriesRegistration, SeriesRosterInvitation


class SeasonSchema(ModelSchema):
    class Config:
        model = Season
        model_fields = "__all__"


class SeriesSchema(ModelSchema):
    teams: list[TeamMinSchema]
    type: str
    category: str

    @staticmethod
    def resolve_type(series: Series) -> str:
        return str(Series.Type._value2member_map_[series.type]._label_)  # type: ignore[attr-defined]

    @staticmethod
    def resolve_category(series: Series) -> str:
        return str(Series.Category._value2member_map_[series.category]._label_)  # type: ignore[attr-defined]

    class Config:
        model = Series
        model_fields = "__all__"


class SeriesMinSchema(ModelSchema):
    type: str
    category: str

    @staticmethod
    def resolve_type(series: Series) -> str:
        return str(Series.Type._value2member_map_[series.type]._label_)  # type: ignore[attr-defined]

    @staticmethod
    def resolve_category(series: Series) -> str:
        return str(Series.Category._value2member_map_[series.category]._label_)  # type: ignore[attr-defined]

    class Config:
        model = Series
        model_fields = ["name", "slug", "start_date", "end_date"]


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
    player_transfer_window_start_date: date | None
    player_transfer_window_end_date: date | None
    season_id: int | None


class SeriesRosterInvitationCreateSchema(Schema):
    to_player_id: int
    expires_on: date | None


class SeriesRosterInvitationSchema(ModelSchema):
    from_user: UserMinSchema
    to_player: PlayerTinySchema
    team: TeamMinSchema

    class Config:
        model = SeriesRosterInvitation
        model_exclude = ["series"]


class AddOrRemoveTeamSeriesRegistrationSchema(Schema):
    team_slug: str


class SeriesRegistrationSchema(ModelSchema):
    team: TeamMinSchema
    player: PlayerTinySchema

    class Config:
        model = SeriesRegistration
        model_fields = "__all__"


class SeriesTeamRosterSchema(ModelSchema):
    player: PlayerMinSchema

    class Config:
        model = SeriesRegistration
        model_fields = ["player"]


class SeriesRegistrationAddSchema(Schema):
    player_id: int
