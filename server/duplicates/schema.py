from datetime import datetime
from typing import Any

from ninja import Schema


class GroupRowSchema(Schema):
    row_id: int
    user_id: int | None
    email: str
    state: str
    since: datetime | None
    is_yours: bool
    merged_into_you: bool
    verified_for_you: bool
    last_seen: str | None
    # How this account was proven: "email-code", "same-inbox", "staff", or
    # "" if not yet confirmed. Shown alongside state, never gated on proof.
    proof: str
    # Only once the viewer has proved they hold this account.
    profile: dict[str, Any] | None = None


class GroupSchema(Schema):
    token: str
    status: str
    origin: str
    expires_at: datetime
    signed_in_as: int | None
    # The viewer's own address when they are signed in to none of these
    # accounts, so the page can say so rather than ask them to sign in.
    signed_in_elsewhere: str | None
    is_requester: bool
    # True only for the requester's own cancellation, never for a dismissal
    # by the other owner — is_requester alone can't tell those apart.
    cancelled_by_you: bool
    can_act: bool
    # A merge happened somewhere in this group. Told even to a viewer who
    # sees no rows, so a finished group is never read as merged when a
    # deletion, not a merge, is what actually closed it (spec §13).
    anything_merged: bool
    rows: list[GroupRowSchema]


class MergeConfirmSchema(Schema):
    # Exactly one: a merge is always the keeper and one other account.
    absorb_user_id: int
    # Field name to the value the person settled on, for the ones that differ.
    resolved: dict[str, Any] = {}


class MergeResultSchema(Schema):
    primary_user_id: int
    merged_user_ids: list[int]
    rows_moved: int


class RowActionSchema(Schema):
    user_id: int


class VerifySchema(Schema):
    user_id: int
    code: str


class StaffRequestSchema(Schema):
    user_id: int
    note: str = ""


class RequestMergeSchema(Schema):
    email: str
    note: str = ""


class RequestedSchema(Schema):
    token: str


class MyGroupSchema(Schema):
    token: str
    origin: str
    # Accounts in the group besides yours that could still be merged.
    waiting: int
    status: str
    # A merge happened in this group. A Resolved group may have closed
    # because its other account was deleted or merged elsewhere instead.
    anything_merged: bool
    # The group is still open but your link to it has expired, so you can
    # no longer act in it; asking again for the address starts a new one.
    # Never true of a finished group, whose links a dismissal also expires.
    expired: bool
    # When the group started (DuplicateCluster.created_at).
    started_at: datetime
    # One other member's address, to label the row. Masked the same way
    # _serialize's shows_address would - which for this authenticated
    # endpoint means never, and hidden entirely where a dismissed group
    # would hide it from a member too (see _visible_rows, spec §5).
    other_email: str | None
    # How many other members the group has (0 when other_email is None).
    # More than 1 means other_email is only one of them.
    other_count: int
