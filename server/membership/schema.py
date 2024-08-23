from typing import Any

from ninja import ModelSchema, Schema

from server.core.models import User
from server.schema import UserFormSchema
from server.tournament.schema import EventSchema

from .models import ManualTransaction, PhonePeTransaction, RazorpayTransaction


class ManualTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> EventSchema | None:
        if transaction.event is not None:
            return EventSchema.from_orm(transaction.event)
        return None

    class Config:
        model = ManualTransaction
        model_fields = "__all__"


class RazorpayTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> EventSchema | None:
        if transaction.event is not None:
            return EventSchema.from_orm(transaction.event)
        return None

    class Config:
        model = RazorpayTransaction
        model_fields = "__all__"


class PhonePeTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> EventSchema | None:
        if transaction.event is not None:
            return EventSchema.from_orm(transaction.event)
        return None

    class Config:
        model = PhonePeTransaction
        model_fields = "__all__"


class ManualTransactionValidationFormSchema(Schema):
    transaction_id: str
    validation_comment: str


class ManualTransactionLiteSchema(ModelSchema):
    class Config:
        model = ManualTransaction
        model_fields = ["transaction_id", "amount", "currency"]


class PhonePePaymentSchema(Schema):
    redirect_url: str
    amount: int


class OrderSchema(Schema):
    order_id: str
    amount: int
    currency: str
    receipt: str
    key: str
    name: str
    image: str
    description: str
    prefill: dict[str, Any]
