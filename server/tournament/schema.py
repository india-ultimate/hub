from typing import Any

from django.db.models import Count, Prefetch, QuerySet
from ninja import Field, ModelSchema, Schema

from server.core.models import CommentaryInfo, Player, Team, UCPerson
from server.schema import (
    PersonSchema,
    PlayerSchema,
    RegistrationCount,
    TeamMinSchema,
    TeamSchema,
)
from server.series.schema import SeriesSchema, TournamentSeriesSchema
from server.utils import full_name

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

    class Meta:
        model = UCRegistration
        fields = "__all__"


class EventSchema(ModelSchema):
    series: SeriesSchema | None = None

    payment_account_name: str | None = None

    @staticmethod
    def resolve_payment_account_name(event: Event) -> str | None:
        if event.payment_account_id is None:  # no query for an event of our own
            return None
        return event.payment_account.name if event.payment_account else None

    class Meta:
        model = Event
        exclude = ["ultimate_central_id"]


class TournamentEventSchema(EventSchema):
    series: TournamentSeriesSchema | None = None  # type: ignore[assignment]


class TournamentMinSchema(ModelSchema):
    event: TournamentEventSchema

    class Meta:
        model = Tournament
        exclude = ["volunteers", "directors"]


class SeriesNameSchema(Schema):
    name: str


class TournamentCardEventSchema(ModelSchema):
    series: SeriesNameSchema | None = None

    class Meta:
        model = Event
        fields = [
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
            *Event.TAG_FIELDS,
        ]


class TournamentCardSchema(ModelSchema):
    event: TournamentCardEventSchema

    class Meta:
        model = Tournament
        fields = ["id", "status", "logo_light", "logo_dark"]


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

    class Meta:
        model = Tournament
        exclude = ["volunteers", "directors"]


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
    is_iu_sanctioned: bool
    age: Event.Age
    surface: Event.Surface
    level: Event.Level
    stage: Event.Stage
    format: Event.Format
    skill_division: Event.SkillDivision | None = None
    is_adaptive: bool = False
    is_subscription_needed: bool


class TournamentUpdateSeedingSchema(Schema):
    seeding: dict[int, int]


class AddOrRemoveTeamRegistrationSchema(Schema):
    team_id: int


class AddToRosterSchema(Schema):
    player_id: int
    is_playing: bool | None = None
    role: str | None = None


class TournamentPlayerRegistrationUpdateSchema(Schema):
    role: str | None = None
    is_playing: bool | None = None


class TournamentPlayerRegistrationSchema(Schema):
    id: int
    team: TeamMinSchema
    player: PlayerSchema
    is_playing: bool
    role: str
    points: float | None = None
    event_name: str
    series_name: str | None = None
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

    class Meta:
        model = Registration


class RosterPointsSchema(Schema):
    points: float


class PoolSchema(ModelSchema):
    class Meta:
        model = Pool
        exclude = ["tournament"]


class PoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


class SwissRoundSchema(ModelSchema):
    class Meta:
        model = SwissRound
        exclude = ["tournament"]


class SwissRoundCreateSchema(Schema):
    num_rounds: int
    seeding: list[int]
    sequence_number: int
    name: str


class CrossPoolSchema(ModelSchema):
    class Meta:
        model = CrossPool
        exclude = ["tournament"]


class BracketSchema(ModelSchema):
    class Meta:
        model = Bracket
        exclude = ["tournament"]


class BracketCreateSchema(Schema):
    sequence_number: int
    name: str


class PositionPoolSchema(ModelSchema):
    class Meta:
        model = PositionPool
        exclude = ["tournament"]


class PositionPoolCreateSchema(Schema):
    seeding: list[int]
    sequence_number: int
    name: str


# Who entered a score, or was named in one, by name only: everyone sees
# these, and pages read nothing else.


class PublicPlayerSchema(Schema):
    id: int
    full_name: str
    slug: str | None = None

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return full_name(player.user)


class PublicPersonSchema(ModelSchema):
    class Meta:
        model = UCPerson
        fields = ["id", "first_name", "last_name", "image_url"]


class PublicMatchScoreSchema(ModelSchema):
    entered_by: PublicPlayerSchema

    class Meta:
        model = MatchScore
        fields = "__all__"


class PublicSpiritScoreSchema(ModelSchema):
    mvp: PublicPersonSchema | None = None
    msp: PublicPersonSchema | None = None
    mvp_v2: PublicPlayerSchema | None = None
    msp_v2: PublicPlayerSchema | None = None

    class Meta:
        model = SpiritScore
        fields = "__all__"


class TournamentFieldSchema(ModelSchema):
    class Meta:
        model = TournamentField
        exclude = ["tournament"]


class TournamentFieldCreateSchema(Schema):
    name: str
    is_broadcasted: bool
    address: str | None = None


class TournamentFieldUpdateSchema(Schema):
    name: str | None = None
    is_broadcasted: bool | None = None
    tournament_id: int
    address: str | None = None


class MatchEventSchema(ModelSchema):
    team: TeamSchema | None = None
    players: list[PublicPlayerSchema]

    @staticmethod
    def resolve_players(match_event: MatchEvent) -> QuerySet[Player]:
        return match_event.players.all().order_by("user__first_name")

    scored_by: PublicPlayerSchema | None = None
    assisted_by: PublicPlayerSchema | None = None
    drop_by: PublicPlayerSchema | None = None
    throwaway_by: PublicPlayerSchema | None = None
    block_by: PublicPlayerSchema | None = None

    class Meta:
        model = MatchEvent
        exclude = ["stats"]


class MatchStatsSchema(ModelSchema):
    initial_possession: TeamSchema
    current_possession: TeamSchema

    events: list[MatchEventSchema]

    @staticmethod
    def resolve_events(match_stats: MatchStats) -> QuerySet[MatchEvent]:
        return MatchEvent.objects.filter(stats=match_stats).order_by("-time")

    class Meta:
        model = MatchStats
        exclude = ["match", "tournament"]


class MatchStatsMinSchema(ModelSchema):
    initial_possession: TeamSchema
    current_possession: TeamSchema

    class Meta:
        model = MatchStats
        exclude = ["match", "tournament"]


class MatchStatsCreateSchema(Schema):
    initial_possession_team_id: int
    initial_ratio: str | None = None


class MatchEventCreateSchema(Schema):
    type: str
    team_id: int
    player_ids: list[int] | None = None
    scored_by_id: int | None = None
    assisted_by_id: int | None = None
    drop_by_id: int | None = None
    throwaway_by_id: int | None = None
    block_by_id: int | None = None


class MatchSchema(ModelSchema):
    pool: PoolSchema | None = None
    cross_pool: CrossPoolSchema | None = None
    bracket: BracketSchema | None = None
    position_pool: PositionPoolSchema | None = None
    swiss_round: SwissRoundSchema | None = None
    team_1: TeamSchema | None = None
    team_2: TeamSchema | None = None
    spirit_score_team_1: PublicSpiritScoreSchema | None = None
    spirit_score_team_2: PublicSpiritScoreSchema | None = None
    self_spirit_score_team_1: PublicSpiritScoreSchema | None = None
    self_spirit_score_team_2: PublicSpiritScoreSchema | None = None
    suggested_score_team_1: PublicMatchScoreSchema | None = None
    suggested_score_team_2: PublicMatchScoreSchema | None = None
    field: TournamentFieldSchema | None = None
    stats: MatchStatsMinSchema | None = None

    @staticmethod
    def resolve_stats(match: Match) -> MatchStats | None:
        try:
            return match.stats
        except MatchStats.DoesNotExist:
            return None

    class Meta:
        model = Match
        exclude = ["tournament"]


# Public GET endpoints: only what a page reads, and nothing personal.


class PublicUCPersonSchema(Schema):
    id: int
    first_name: str
    last_name: str
    image_url: str | None = None
    # Only the gender the roster shows, never the rest of the player.
    player: dict[str, str] | None = None


class PublicUCRegistrationSchema(Schema):
    id: int
    roles: list[str]
    team: TeamMinSchema
    person: PublicUCPersonSchema

    @staticmethod
    def resolve_person(registration: UCRegistration) -> dict[str, Any]:
        person = registration.person
        gender = getattr(registration, "player_gender", None)
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "image_url": person.image_url,
            "player": {"gender": gender} if gender else None,
        }


class PublicStageSchema(Schema):
    id: int
    name: str
    sequence_number: int


class PublicCrossPoolSchema(Schema):
    id: int


class PublicMatchStatsMinSchema(ModelSchema):
    initial_possession: TeamMinSchema
    current_possession: TeamMinSchema

    class Meta:
        model = MatchStats
        exclude = ["match", "tournament"]


class PublicMatchSchema(ModelSchema):
    pool: PublicStageSchema | None = None
    cross_pool: PublicCrossPoolSchema | None = None
    bracket: PublicStageSchema | None = None
    position_pool: PublicStageSchema | None = None
    swiss_round: PublicStageSchema | None = None
    team_1: TeamMinSchema | None = None
    team_2: TeamMinSchema | None = None
    spirit_score_team_1: PublicSpiritScoreSchema | None = None
    spirit_score_team_2: PublicSpiritScoreSchema | None = None
    self_spirit_score_team_1: PublicSpiritScoreSchema | None = None
    self_spirit_score_team_2: PublicSpiritScoreSchema | None = None
    suggested_score_team_1: PublicMatchScoreSchema | None = None
    suggested_score_team_2: PublicMatchScoreSchema | None = None
    field: TournamentFieldSchema | None = None
    stats: PublicMatchStatsMinSchema | None = None

    @staticmethod
    def resolve_stats(match: Match) -> MatchStats | None:
        try:
            return match.stats
        except MatchStats.DoesNotExist:
            return None

    class Meta:
        model = Match
        exclude = ["tournament"]


class MatchTournamentSchema(Schema):
    slug: str = Field(alias="event.slug")
    title: str = Field(alias="event.title")


class RecentMatchSchema(PublicMatchSchema):
    """A match on the website's schedule, which spans tournaments."""

    tournament: MatchTournamentSchema


_SPIRIT_SCORES = [
    "spirit_score_team_1",
    "spirit_score_team_2",
    "self_spirit_score_team_1",
    "self_spirit_score_team_2",
]


def public_matches(matches: QuerySet[Match]) -> QuerySet[Match]:
    """Matches with everything `PublicMatchSchema` sends, in five queries.

    Not one: joining all 45 tables took Postgres 30 ms just to plan, on
    every request. The spirit scores and their people come in four small
    queries instead.
    """
    spirit = SpiritScore.objects.select_related("mvp", "msp", "mvp_v2__user", "msp_v2__user")
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
    ).prefetch_related(*(Prefetch(score, queryset=spirit) for score in _SPIRIT_SCORES))


class PublicMatchEventSchema(ModelSchema):
    team: TeamMinSchema | None = None
    players: list[PublicPlayerSchema]
    scored_by: PublicPlayerSchema | None = None
    assisted_by: PublicPlayerSchema | None = None
    drop_by: PublicPlayerSchema | None = None
    throwaway_by: PublicPlayerSchema | None = None
    block_by: PublicPlayerSchema | None = None

    @staticmethod
    def resolve_players(match_event: MatchEvent) -> list[Player]:
        return list(match_event.players.all())  # prefetched, in name order

    class Meta:
        model = MatchEvent
        exclude = ["stats"]


class PublicMatchStatsSchema(ModelSchema):
    initial_possession: TeamMinSchema
    current_possession: TeamMinSchema
    events: list[PublicMatchEventSchema]

    @staticmethod
    def resolve_events(match_stats: MatchStats) -> list[MatchEvent]:
        return list(match_stats.events.all())  # prefetched, newest first

    class Meta:
        model = MatchStats
        exclude = ["match", "tournament"]


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
    rules: int = Field(ge=0, le=4)
    fouls: int = Field(ge=0, le=4)
    fair: int = Field(ge=0, le=4)
    positive: int = Field(ge=0, le=4)
    communication: int = Field(ge=0, le=4)

    mvp_id: str | None = None
    msp_id: str | None = None

    comments: str | None = Field(default=None, max_length=500)


class SpiritScoreSubmitSchema(Schema):
    opponent: SpiritScoreUpdateSchema
    self: SpiritScoreUpdateSchema

    team_id: int


class MatchUpdateSchema(Schema):
    time: str | None = None
    field_id: int | None = None
    video_url: str | None = None
    duration_mins: int | None = None
    spirit_score_team_1: SpiritScoreUpdateSchema | None = None
    spirit_score_team_2: SpiritScoreUpdateSchema | None = None
    self_spirit_score_team_1: SpiritScoreUpdateSchema | None = None
    self_spirit_score_team_2: SpiritScoreUpdateSchema | None = None


class MatchScoreSchema(Schema):
    team_1_score: int = Field(ge=0)
    team_2_score: int = Field(ge=0)


class TournamentRulesSchema(Schema):
    rules: str


class PublicCommentaryInfoSchema(Schema):
    jersey_number: int


class PublicRosterPlayerSchema(Schema):
    id: int
    full_name: str
    slug: str | None = None
    profile_pic_url: str | None = None
    gender: str
    commentary_info: PublicCommentaryInfoSchema | None = None

    @staticmethod
    def resolve_full_name(player: Player) -> str:
        return full_name(player.user)

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
