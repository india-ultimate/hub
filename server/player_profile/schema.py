import datetime

from ninja import Schema

from server.schema import TeamMinSchema


class ProfileStatsSchema(Schema):
    goals: int
    assists: int
    blocks: int
    games: int


class ProfileTournamentSchema(Schema):
    slug: str
    title: str
    start_date: datetime.date
    end_date: datetime.date
    location: str
    logo_light: str | None
    logo_dark: str | None
    status: str
    team: TeamMinSchema
    role: str
    is_playing: bool
    placement: int | None
    stats: ProfileStatsSchema | None
    mvp: int
    msp: int


class PlayerProfileSchema(Schema):
    slug: str
    full_name: str
    profile_pic_url: str | None
    match_up: str
    state: str | None
    jersey_number: int | None
    current_team: TeamMinSchema | None
    tournaments: list[ProfileTournamentSchema]
