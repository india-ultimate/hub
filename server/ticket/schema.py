from datetime import datetime

from ninja import Schema


class TicketCreateSchema(Schema):
    title: str
    description: str
    priority: str = "MED"
    category: str | None = None


class TicketUpdateSchema(Schema):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    assigned_to_id: int | None = None


class TicketMessageCreateSchema(Schema):
    message: str


class UserSchema(Schema):
    id: int
    username: str
    first_name: str
    last_name: str


class TicketMessageSchema(Schema):
    id: int
    message: str
    sender: UserSchema
    created_at: datetime
    attachment: str | None = None


class TicketDetailSchema(Schema):
    id: int
    title: str
    description: str
    status: str
    priority: str
    category: str | None
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
    category: str | None
    created_at: datetime
    created_by: UserSchema
    assigned_to: UserSchema | None = None
    message_count: int
