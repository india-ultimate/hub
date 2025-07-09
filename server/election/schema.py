from datetime import datetime

from ninja import Schema


class ErrorSchema(Schema):
    message: str


class UserSchema(Schema):
    id: int
    username: str
    full_name: str


class WinnerSchema(Schema):
    id: int
    name: str
    votes: int


class ElectionSchema(Schema):
    id: int
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    is_active: bool
    num_winners: int
    voting_method: str
    created_at: datetime
    updated_at: datetime
    winners: list[WinnerSchema] | None = None


class ElectionCreateSchema(Schema):
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    num_winners: int = 1
    voting_method: str = "IRV"


class CandidateSchema(Schema):
    id: int
    election_id: int
    user_id: int
    bio: str
    created_at: datetime
    user: UserSchema
    manifesto_link: str | None = None


class CandidateCreateSchema(Schema):
    user_id: int
    bio: str


class RankedVoteChoiceSchema(Schema):
    candidate_id: int
    rank: int


class VoterVerificationSchema(Schema):
    verification_token: str
    created_at: datetime
    is_used: bool


class WardVoterVerificationSchema(Schema):
    id: int
    name: str
    email: str
    is_used: bool
    verification_token: str


class RankedVoteCreateSchema(Schema):
    verification_token: str
    choices: list[RankedVoteChoiceSchema]


class RankedVoteSchema(Schema):
    id: int
    election_id: int
    voter_hash: str
    timestamp: datetime


class CandidateResultSchema(Schema):
    id: int
    name: str
    votes: int
    status: str


class RoundResultSchema(Schema):
    candidates: list[CandidateResultSchema]


class ElectionResultSchema(Schema):
    rounds: list[RoundResultSchema]


class EligibleVoterSchema(Schema):
    id: int
    election_id: int
    user_id: int
    created_at: datetime
    user: UserSchema
