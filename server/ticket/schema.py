from datetime import datetime
from typing import Any

from ninja import Schema
from pydantic import Field, field_validator

from server.committee.routing import committees_for
from server.core.models import User
from server.schema import profile_pic_url, viewer_is_staff
from server.ticket.access import can_handle
from server.ticket.models import Ticket


def _blank_is_none(value: object) -> object:
    # The create form sends "" for "no category"
    return value or None


class TicketCreateSchema(Schema):
    title: str
    description: str
    priority: str = "MED"
    category: str | None = None
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
    category: str | None = None
    is_private: bool | None = None

    @field_validator("category", mode="before")
    @classmethod
    def _category(cls, value: object) -> object:
        return _blank_is_none(value)


class UserSchema(Schema):
    id: int
    first_name: str
    last_name: str
    # An email: staff mail people from the ticket page, no one else sees it.
    username: str | None = None

    @staticmethod
    def resolve_username(user: User, context: dict[str, Any]) -> str | None:
        return user.username if viewer_is_staff(context) else None


class AssigneeSchema(UserSchema):
    profile_pic_url: str | None = None

    @staticmethod
    def resolve_profile_pic_url(user: User) -> str | None:
        return profile_pic_url(user)


class TicketMessageCreateSchema(Schema):
    message: str


class TicketMessageSchema(Schema):
    id: int
    message: str
    sender: UserSchema
    created_at: datetime
    attachment: str | None = None  # URL to the attachment (Cloudinary)


class TicketCategoryFields(Schema):
    # The key tickets store, and the name people see
    category: str | None = Field(None, alias="category_id")
    category_name: str | None = None

    @staticmethod
    def resolve_category_name(ticket: Ticket) -> str | None:
        return ticket.category.name if ticket.category else None


class TicketDetailSchema(TicketCategoryFields):
    id: int
    title: str
    description: str
    status: str
    priority: str
    is_private: bool
    upvote_count: int
    has_upvoted: bool
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None = None
    created_by: UserSchema
    assignees: list[AssigneeSchema]
    messages: list[TicketMessageSchema]
    can_handle: bool
    # The title and description: only their author and staff
    can_edit: bool
    # Slugs, so the assignee picker can list these committees first
    routed_committees: list[str]

    @staticmethod
    def resolve_can_handle(ticket: Ticket, context: dict[str, Any]) -> bool:
        return can_handle(context["request"].user, ticket)

    @staticmethod
    def resolve_can_edit(ticket: Ticket, context: dict[str, Any]) -> bool:
        user = context["request"].user
        return bool(user.is_staff or ticket.created_by_id == user.id)

    @staticmethod
    def resolve_routed_committees(ticket: Ticket) -> list[str]:
        return list(committees_for(ticket.category_id).values_list("slug", flat=True))


class TicketListItemSchema(TicketCategoryFields):
    id: int
    title: str
    status: str
    priority: str
    is_private: bool
    upvote_count: int
    has_upvoted: bool
    created_at: datetime
    created_by: UserSchema
    assignees: list[AssigneeSchema]
    message_count: int
    # How well it matched a search; None when there were no words to search for
    score: int | None = None


class TicketCategorySchema(Schema):
    key: str
    name: str
    order: int
    is_retired: bool


class TicketCategoryCreateSchema(Schema):
    name: str


class TicketCategoryUpdateSchema(Schema):
    name: str | None = None
    order: int | None = None
    is_retired: bool | None = None


class TicketRouteSchema(Schema):
    category: str
    committees: list[str]


class TicketRouteUpdateSchema(Schema):
    committees: list[str]
