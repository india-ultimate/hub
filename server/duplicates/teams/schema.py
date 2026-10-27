from ninja import Schema


class TeamIdsSchema(Schema):
    team_ids: list[int]


class MergeTeamsSchema(TeamIdsSchema):
    keeper_id: int
    # The team whose logo the kept team takes; the keeper's own if not given.
    logo_id: int | None = None
    # Why the teams are one, for staff. Only asked for when they must approve.
    message: str = ""


class ColumnSchema(Schema):
    id: int
    name: str
    slug: str | None
    logo: str | None
    label: str


class LineSchema(Schema):
    label: str
    values: list[str]
    differs: bool


class PreviewSchema(Schema):
    teams: list[ColumnSchema]
    lines: list[LineSchema]
    blockers: list[str]
    keeper_id: int
    # True when the person admins every team, so the merge needs no approval.
    can_merge: bool
    # The teams the person admins; staff check the rest.
    admin_of: list[int]
    # A request for any of these teams is already waiting for staff.
    pending: bool


class OutcomeSchema(Schema):
    merged: bool
    slug: str | None = None
    request_id: int | None = None


class CopySchema(ColumnSchema):
    city: str | None
    category: str
    tournaments: int


class SuggestionSchema(Schema):
    team: ColumnSchema
    copies: list[CopySchema]
    # Staff are already looking at a merge of this team.
    pending: bool


class PairSchema(Schema):
    team_id: int
    other_id: int
