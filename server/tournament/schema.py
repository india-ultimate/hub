from django.db.models import Count, Prefetch, QuerySet
from ninja import ModelSchema, Schema

from server.core.models import CommentaryInfo, Player, Team, UCPerson
from server.schema import (
    PersonSchema,
    PlayerSchema,
    PlayerTinySchema,
    RegistrationCount,
    TeamMinSchema,
    TeamSchema,
)
from server.series.schema import SeriesSchema, TournamentSeriesSchema

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
    SwissRound,
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

    payment_account_name: str | None

    @staticmethod
    def resolve_payment_account_name(event: Event) -> str | None:
        if event.payment_account_id is None:  # no query for an event of our own
            return None
        return event.payment_account.name if event.payment_account else None

    class Config:
        model = Event
        model_exclude = ["ultimate_central_id"]


class TournamentEventSchema(EventSchema):
    series: TournamentSeriesSchema | None  # type: ignore[assignment]


class TournamentMinSchema(ModelSchema):
    event: TournamentEventSchema

    class Config:
        model = Tournament
        model_exclude = ["volunteers", "directors"]


class SeriesNameSchema(Schema):
    name: str


class TournamentCardEventSchema(ModelSchema):
    series: SeriesNameSchema | None

    class Config:
        model = Event
        model_fields = [
            "id",
            "title",
            "type",
            "slug",
            "location",
            "start_date",
            "end_date",
            "team_registration_start_date",
            "team_registration_end_date",
            "team_partial_registration_end_date",
            "team_late_penalty_end_date",
            "player_registration_start_date",
            "player_registration_end_date",
            "player_late_penalty_end_date",
        ]


class TournamentCardSchema(ModelSchema):
    event: TournamentCardEventSchema

    class Config:
        model = Tournament
        model_fields = ["id", "status", "logo_light", "logo_dark"]


class TournamentCardsSchema(Schema):
    years: list[int]
    tournaments: list[TournamentCardSchema]


class TournamentSchema(ModelSchema):
    event: TournamentEventSchema
    teams: list[TeamMinSchema]
    partial_teams: list[TeamMinSchema]

    @staticmethod
    def resolve_teams(tournament: Tournament) -> QuerySet[Team]:
        return tournament.teams.all().order_by("name")

    @staticmethod
    def resolve_partial_teams(tournament: Tournament) -> QuerySet[Team]:
        return tournament.partial_teams.all().order_by("name")

    reg_count: list[RegistrationCount]

    @staticmethod
    def resolve_reg_count(tournament: Tournament) -> list[RegistrationCount]:
        rows = (
            Registration.objects.filter(event=tournament.event_id)
            .values_list("team")
            .annotate(count=Count("id"))
        )
        counts = {row[0]: row[1] for row in rows}
        return [
            RegistrationCount(team_id=team.id, count=counts.get(team.id, 0))
            for team in tournament.teams.all()
        ]

    class Config:
        model = Tournament
        model_exclude = ["volunteers", "directors"]


class TournamentCreateFromEventSchema(Schema):
    event_id: int


class TournamentDirectorAddSchema(Schema):
    user_id: int


class TournamentCreateSchema(Schema):
    title: str
    start_date: str
    end_date: str
    team_registration_start_date: str
    team_registration_end_date: str
    player_registration_start_date: str
    player_registration_end_date: str
    team_partial_registration_end_date: str
    team_late_penalty_end_date: str
    player_late_penalty_end_date: str
    location: str
    type: str
    team_fee: int
    player_fee: int
    partial_team_fee: int
    team_late_penalty: int
    player_late_penalty: int


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
    team: TeamMinSchema
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


class SwissRoundSchema(ModelSchema):
    class Config:
        model = SwissRound
        model_exclude = ["tournament"]


class SwissRoundCreateSchema(Schema):
    num_rounds: int
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
    swiss_round: SwissRoundSchema | None
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


# Public GET endpoints: only what a page reads, and nothing personal.


class PublicPlayerSchema(Schema):
    id: int
    full_name: str

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()


class PublicPersonSchema(ModelSchema):
    class Config:
        model = UCPerson
        model_fields = ["first_name", "last_name", "image_url"]


class PublicStageSchema(Schema):
    id: int
    name: str
    sequence_number: int


class PublicCrossPoolSchema(Schema):
    id: int


class PublicSpiritScoreSchema(ModelSchema):
    mvp: PublicPersonSchema | None
    msp: PublicPersonSchema | None
    mvp_v2: PublicPlayerSchema | None
    msp_v2: PublicPlayerSchema | None

    class Config:
        model = SpiritScore
        model_fields = "__all__"


class PublicMatchScoreSchema(ModelSchema):
    entered_by: PublicPlayerSchema

    class Config:
        model = MatchScore
        model_fields = "__all__"


class PublicMatchStatsMinSchema(ModelSchema):
    initial_possession: TeamMinSchema
    current_possession: TeamMinSchema

    class Config:
        model = MatchStats
        model_exclude = ["match", "tournament"]


class PublicMatchSchema(ModelSchema):
    pool: PublicStageSchema | None
    cross_pool: PublicCrossPoolSchema | None
    bracket: PublicStageSchema | None
    position_pool: PublicStageSchema | None
    swiss_round: PublicStageSchema | None
    team_1: TeamMinSchema | None
    team_2: TeamMinSchema | None
    spirit_score_team_1: PublicSpiritScoreSchema | None
    spirit_score_team_2: PublicSpiritScoreSchema | None
    self_spirit_score_team_1: PublicSpiritScoreSchema | None
    self_spirit_score_team_2: PublicSpiritScoreSchema | None
    suggested_score_team_1: PublicMatchScoreSchema | None
    suggested_score_team_2: PublicMatchScoreSchema | None
    field: TournamentFieldSchema | None
    stats: PublicMatchStatsMinSchema | None

    @staticmethod
    def resolve_stats(match: Match) -> MatchStats | None:
        try:
            return match.stats
        except MatchStats.DoesNotExist:
            return None

    class Config:
        model = Match
        model_exclude = ["tournament"]


_SPIRIT_SCORES = [
    "spirit_score_team_1",
    "spirit_score_team_2",
    "self_spirit_score_team_1",
    "self_spirit_score_team_2",
]


def public_matches(matches: QuerySet[Match]) -> QuerySet[Match]:
    """Matches with everything `PublicMatchSchema` sends, in one query."""
    # ponytail: one wide join (about 45 tables); if Postgres plans it
    # slowly, move the spirit scores' people to prefetch_related.
    return matches.select_related(
        "pool",
        "cross_pool",
        "bracket",
        "position_pool",
        "swiss_round",
        "team_1",
        "team_2",
        "field",
        "suggested_score_team_1__entered_by__user",
        "suggested_score_team_2__entered_by__user",
        "stats__initial_possession",
        "stats__current_possession",
        *(f"{score}__{person}" for score in _SPIRIT_SCORES for person in ("mvp", "msp")),
        *(f"{score}__{p}__user" for score in _SPIRIT_SCORES for p in ("mvp_v2", "msp_v2")),
    )


class PublicMatchEventSchema(ModelSchema):
    team: TeamMinSchema | None
    players: list[PublicPlayerSchema]
    scored_by: PublicPlayerSchema | None
    assisted_by: PublicPlayerSchema | None
    drop_by: PublicPlayerSchema | None
    throwaway_by: PublicPlayerSchema | None
    block_by: PublicPlayerSchema | None

    @staticmethod
    def resolve_players(match_event: MatchEvent) -> list[Player]:
        return list(match_event.players.all())  # prefetched, in name order

    class Config:
        model = MatchEvent
        model_exclude = ["stats"]


class PublicMatchStatsSchema(ModelSchema):
    initial_possession: TeamMinSchema
    current_possession: TeamMinSchema
    events: list[PublicMatchEventSchema]

    @staticmethod
    def resolve_events(match_stats: MatchStats) -> list[MatchEvent]:
        return list(match_stats.events.all())  # prefetched, newest first

    class Config:
        model = MatchStats
        model_exclude = ["match", "tournament"]


_EVENT_PLAYERS = ["scored_by", "assisted_by", "drop_by", "throwaway_by", "block_by"]


def public_match_stats(stats: QuerySet[MatchStats]) -> QuerySet[MatchStats]:
    """Stats with everything `PublicMatchStatsSchema` sends, in 3 queries."""
    events = MatchEvent.objects.order_by("-time").select_related(
        "team", *(f"{p}__user" for p in _EVENT_PLAYERS)
    )
    players = Player.objects.select_related("user").order_by("user__first_name")
    return stats.select_related("initial_possession", "current_possession").prefetch_related(
        Prefetch("events", queryset=events),
        Prefetch("events__players", queryset=players),
    )


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


class PublicCommentaryInfoSchema(Schema):
    jersey_number: int


class PublicRosterPlayerSchema(Schema):
    id: int
    full_name: str
    profile_pic_url: str | None
    gender: str
    commentary_info: PublicCommentaryInfoSchema | None

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return player.user.get_full_name()

    @staticmethod
    def resolve_commentary_info(player: Player) -> CommentaryInfo | None:
        try:
            return player.commentary_info
        except CommentaryInfo.DoesNotExist:
            return None


class PublicRosterEntrySchema(Schema):
    id: int
    event_id: int
    team: TeamMinSchema
    player: PublicRosterPlayerSchema
    is_playing: bool
    role: str
