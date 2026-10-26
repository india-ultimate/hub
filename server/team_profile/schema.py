import datetime

from ninja import Schema

from server.schema import TeamMinSchema


class AdminSchema(Schema):
    full_name: str
    slug: str | None


class RecordSchema(Schema):
    played: int
    wins: int
    losses: int
    draws: int


class FormSchema(Schema):
    tournament_slug: str
    tournament_title: str
    date: datetime.date
    opponent: TeamMinSchema
    score_for: int
    score_against: int
    result: str


class RivalSchema(Schema):
    team: TeamMinSchema
    played: int
    wins: int
    losses: int


class PlayerSchema(Schema):
    slug: str | None
    full_name: str
    profile_pic_url: str | None


class RosterPlayerSchema(PlayerSchema):
    role: str
    is_playing: bool


class RosterSchema(Schema):
    division: str
    start_date: datetime.date
    season: str
    tournament_slug: str
    tournament_title: str
    players: list[RosterPlayerSchema]


class LeaderSchema(Schema):
    player: PlayerSchema
    value: int


class LeadersSchema(Schema):
    goals: list[LeaderSchema]
    assists: list[LeaderSchema]
    blocks: list[LeaderSchema]
    mvp: list[LeaderSchema]
    msp: list[LeaderSchema]


class TournamentRecordSchema(Schema):
    wins: int
    losses: int
    draws: int


class TournamentSchema(Schema):
    slug: str
    title: str
    start_date: datetime.date
    end_date: datetime.date
    location: str
    logo_light: str | None
    logo_dark: str | None
    status: str
    division: str
    placement: int | None
    spirit_rank: int | None
    record: TournamentRecordSchema | None


class RankingSchema(Schema):
    rank: int
    division: str
    label: str
    tier: str | None
    tournament_slug: str
    tournament_title: str
    year: int


class TeamProfileSchema(Schema):
    id: int
    slug: str | None
    name: str
    image: str | None
    image_url: str | None
    category: str
    city: str | None
    state: str | None
    admins: list[AdminSchema]
    record: RecordSchema | None
    spirit: float | None
    form: list[FormSchema]
    rivals: list[RivalSchema]
    rankings: list[RankingSchema]
    rosters: list[RosterSchema]
    leaders: LeadersSchema
    tournaments: list[TournamentSchema]
