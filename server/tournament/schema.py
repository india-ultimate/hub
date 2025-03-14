from django.db.models import QuerySet
from ninja import ModelSchema, Schema

from server.core.models import Player, Team
from server.schema import (
    PersonSchema,
    PlayerSchema,
    PlayerTinySchema,
    RegistrationCount,
    TeamSchema,
)
from server.series.schema import SeriesSchema

from .models import (
    Bracket,
    CrossPool,
    Event,
    Match,
    MatchEvent,
    MatchScore,
    MatchStats,
    Pool,
    PositionPool,
    Registration,
    SpiritScore,
    Tournament,
    TournamentField,
    UCRegistration,
)


class UCRegistrationSchema(ModelSchema):
    team: TeamSchema
    person: PersonSchema

    class Config:
        model = UCRegistration
        model_fields = "__all__"


class EventSchema(ModelSchema):
    series: SeriesSchema | None

    class Config:
        model = Event
        model_exclude = ["ultimate_central_id"]


class TournamentMinSchema(ModelSchema):
    event: EventSchema

    class Config:
        model = Tournament
        model_exclude = ["volunteers"]


class TournamentSchema(ModelSchema):
    event: EventSchema
    teams: list[TeamSchema]
    partial_teams: list[TeamSchema]

    @staticmethod
    def resolve_teams(tournament: Tournament) -> QuerySet[Team]:
        return tournament.teams.all().order_by("name")

    @staticmethod
    def resolve_partial_teams(tournament: Tournament) -> QuerySet[Team]:
        return tournament.partial_teams.all().order_by("name")

    reg_count: list[RegistrationCount]

    @staticmethod
    def resolve_reg_count(tournament: Tournament) -> list[RegistrationCount]:
        teams = tournament.teams.all()
        return [
            RegistrationCount(
                team_id=team.id,
                count=Registration.objects.filter(team=team, event=tournament.event).count(),
            )
            for team in teams
        ]

    class Config:
        model = Tournament
        model_fields = "__all__"


class TournamentCreateFromEventSchema(Schema):
    event_id: int


class TournamentCreateSchema(Schema):
    title: str
    start_date: str
    end_date: str
    team_registration_start_date: str
    team_registration_end_date: str
    player_registration_start_date: str
    player_registration_end_date: str
    location: str
    type: str


class TournamentUpdateSeedingSchema(Schema):
    seeding: dict[int, int]


class AddOrRemoveTeamRegistrationSchema(Schema):
    team_id: int


class AddToRosterSchema(Schema):
    player_id: int
    is_playing: bool | None
    role: str | None


class TournamentPlayerRegistrationUpdateSchema(Schema):
    role: str | None
    is_playing: bool | None


class TournamentPlayerRegistrationSchema(Schema):
    id: int
    team_id: int
    player: PlayerSchema
    is_playing: bool
    role: str
    points: float | None
    event_name: str
    series_name: str | None
    event_id: int

    @staticmethod
    def resolve_event_name(registration: Registration) -> str:
        return registration.event.title

    @staticmethod
    def resolve_series_name(registration: Registration) -> str | None:
        series = registration.event.series

        if series is None:
            return None

        return series.name

    # @staticmethod
    # def resolve_role_full(registration: Registration) -> str:
    #     return Registration.Role._value2member_map_[registration.role]._label_  # type: ignore[attr-defined]

    class Config:
        model = Registration


class RosterPointsSchema(Schema):
    points: float


class PoolSchema(ModelSchema):
    class Config:
        model = Pool
        model_exclude = ["tournament"]


class PoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


class CrossPoolSchema(ModelSchema):
    class Config:
        model = CrossPool
        model_exclude = ["tournament"]


class BracketSchema(ModelSchema):
    class Config:
        model = Bracket
        model_exclude = ["tournament"]


class BracketCreateSchema(Schema):
    sequence_number: int
    name: str


class PositionPoolSchema(ModelSchema):
    class Config:
        model = PositionPool
        model_exclude = ["tournament"]


class PositionPoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


class MatchScoreModelSchema(ModelSchema):
    entered_by: PlayerTinySchema

    class Config:
        model = MatchScore
        model_fields = "__all__"


class SpiritScoreSchema(ModelSchema):
    mvp: PersonSchema | None
    msp: PersonSchema | None
    mvp_v2: PlayerTinySchema | None
    msp_v2: PlayerTinySchema | None

    class Config:
        model = SpiritScore
        model_fields = "__all__"


class TournamentFieldSchema(ModelSchema):
    class Config:
        model = TournamentField
        model_exclude = ["tournament"]


class TournamentFieldCreateSchema(Schema):
    name: str
    is_broadcasted: bool
    address: str | None


class TournamentFieldUpdateSchema(Schema):
    name: str | None
    is_broadcasted: bool | None
    tournament_id: int
    address: str | None


class MatchEventSchema(ModelSchema):
    team: TeamSchema | None
    players: list[PlayerTinySchema]

    @staticmethod
    def resolve_players(match_event: MatchEvent) -> QuerySet[Player]:
        return match_event.players.all().order_by("user__first_name")

    scored_by: PlayerTinySchema | None
    assisted_by: PlayerTinySchema | None
    drop_by: PlayerTinySchema | None
    throwaway_by: PlayerTinySchema | None
    block_by: PlayerTinySchema | None

    class Config:
        model = MatchEvent
        model_exclude = ["stats"]


class MatchStatsSchema(ModelSchema):
    initial_possession: TeamSchema
    current_possession: TeamSchema

    events: list[MatchEventSchema]

    @staticmethod
    def resolve_events(match_stats: MatchStats) -> QuerySet[MatchEvent]:
        return MatchEvent.objects.filter(stats=match_stats).order_by("-time")

    class Config:
        model = MatchStats
        model_exclude = ["match", "tournament"]


class MatchStatsMinSchema(ModelSchema):
    initial_possession: TeamSchema
    current_possession: TeamSchema

    class Config:
        model = MatchStats
        model_exclude = ["match", "tournament"]


class MatchStatsCreateSchema(Schema):
    initial_possession_team_id: int
    initial_ratio: str | None


class MatchEventCreateSchema(Schema):
    type: str
    team_id: int
    player_ids: list[int] | None
    scored_by_id: int | None
    assisted_by_id: int | None
    drop_by_id: int | None
    throwaway_by_id: int | None
    block_by_id: int | None


class MatchSchema(ModelSchema):
    pool: PoolSchema | None
    cross_pool: CrossPoolSchema | None
    bracket: BracketSchema | None
    position_pool: PositionPoolSchema | None
    team_1: TeamSchema | None
    team_2: TeamSchema | None
    spirit_score_team_1: SpiritScoreSchema | None
    spirit_score_team_2: SpiritScoreSchema | None
    self_spirit_score_team_1: SpiritScoreSchema | None
    self_spirit_score_team_2: SpiritScoreSchema | None
    suggested_score_team_1: MatchScoreModelSchema | None
    suggested_score_team_2: MatchScoreModelSchema | None
    field: TournamentFieldSchema | None
    stats: MatchStatsMinSchema | None

    @staticmethod
    def resolve_stats(match: Match) -> MatchStatsMinSchema | None:
        try:
            return MatchStatsMinSchema.from_orm(match.stats)
        except MatchStats.DoesNotExist:
            return None

    class Config:
        model = Match
        model_exclude = ["tournament"]


class MatchCreateSchema(Schema):
    stage: str
    stage_id: int
    seq_num: int
    time: str
    field_id: int
    seed_1: int
    seed_2: int


class SpiritScoreUpdateSchema(Schema):
    rules: int
    fouls: int
    fair: int
    positive: int
    communication: int

    mvp_id: str | None
    msp_id: str | None

    comments: str | None


class SpiritScoreSubmitSchema(Schema):
    opponent: SpiritScoreUpdateSchema
    self: SpiritScoreUpdateSchema

    team_id: int


class MatchUpdateSchema(Schema):
    time: str | None
    field_id: int | None
    video_url: str | None
    duration_mins: int | None
    spirit_score_team_1: SpiritScoreUpdateSchema | None
    spirit_score_team_2: SpiritScoreUpdateSchema | None
    self_spirit_score_team_1: SpiritScoreUpdateSchema | None
    self_spirit_score_team_2: SpiritScoreUpdateSchema | None


class MatchScoreSchema(Schema):
    team_1_score: int
    team_2_score: int


class TournamentRulesSchema(Schema):
    rules: str
