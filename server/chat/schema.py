from datetime import datetime

from ninja import Schema


class MessageSchema(Schema):
    message: str


class MessageResponseSchema(Schema):
    response: str


class ChatMessageSchema(Schema):
    type: str
    message: str
    timestamp: datetime


class ChatHistorySchema(Schema):
    session_id: int
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageSchema]


class ErrorSchema(Schema):
    message: str


class SuccessSchema(Schema):
    message: str
