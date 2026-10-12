from datetime import datetime

from ninja import Schema
from pydantic import field_validator

from server.ticket.models import Ticket


def _blank_is_none(value: object) -> object:
    # The create form sends "" for "no category"
    return value or None


class TicketCreateSchema(Schema):
    title: str
    description: str
    priority: str = "MED"
    category: Ticket.Category | None = None
    is_private: bool = False

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: object) -> object:
        return _blank_is_none(value)


class TicketUpdateSchema(Schema):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    category: Ticket.Category | None = None
    assigned_to_id: int | None = None
    is_private: bool | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: object) -> object:
        return _blank_is_none(value)


class UserSchema(Schema):
    id: int
    username: str
    first_name: str
    last_name: str


class TicketMessageCreateSchema(Schema):
    message: str


class TicketMessageSchema(Schema):
    id: int
    message: str
    sender: UserSchema
    created_at: datetime
    attachment: str | None = None  # URL to the attachment (Cloudinary)


class TicketDetailSchema(Schema):
    id: int
    title: str
    description: str
    status: str
    priority: str
    category: str | None = None
    is_private: bool
    upvote_count: int
    has_upvoted: bool
    created_at: datetime
    updated_at: datetime
    created_by: UserSchema
    assigned_to: UserSchema | None = None
    messages: list[TicketMessageSchema]


class TicketListItemSchema(Schema):
    id: int
    title: str
    status: str
    priority: str
    category: str | None = None
    is_private: bool
    upvote_count: int
    has_upvoted: bool
    created_at: datetime
    created_by: UserSchema
    assigned_to: UserSchema | None = None
    message_count: int
    # How well it matched a search; None when there were no words to search for
    score: int | None = None
