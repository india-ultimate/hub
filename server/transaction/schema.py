from typing import Any

from ninja import ModelSchema, Schema

from server.core.models import User
from server.schema import UserFormSchema
from server.tournament.models import Event
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

    event: EventSchema | None = None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> Event | None:
        return transaction.event

    class Meta:
        model = ManualTransaction
        fields = "__all__"


class RazorpayTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None = None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> Event | None:
        return transaction.event

    class Meta:
        model = RazorpayTransaction
        fields = "__all__"


class PhonePeTransactionSchema(ModelSchema):
    user: UserFormSchema

    @staticmethod
    def resolve_user(transaction: RazorpayTransaction) -> User:
        return transaction.user

    players: list[str]

    @staticmethod
    def resolve_players(transaction: RazorpayTransaction) -> list[str]:
        return [p.user.get_full_name() for p in transaction.players.all()]

    event: EventSchema | None = None

    @staticmethod
    def resolve_event(transaction: RazorpayTransaction) -> Event | None:
        return transaction.event

    class Meta:
        model = PhonePeTransaction
        fields = "__all__"


class ManualTransactionValidationFormSchema(Schema):
    transaction_id: str
    validation_comment: str


class RazorpayOrderSchema(Schema):
    order_id: str
    amount: int
    currency: str
    receipt: str
    key: str
    name: str
    image: str
    description: str
    prefill: dict[str, Any]


class OrderLineSchema(Schema):
    particulars: str
    people: list[str]
    quantity: int
    rate: int | None
    amount: int


class PayOrderSchema(RazorpayOrderSchema):
    """An unpaid order for the pay page: checkout's fields, and what it buys."""

    issues_receipt: bool
    lines: list[OrderLineSchema]


class RazorpayCallbackSchema(Schema):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class SubscriptionOrderItem(Schema):
    player_id: int
    plan_type: str


class SubscriptionOrderSchema(Schema):
    """What each person is buying. The server prices it; no amount is sent."""

    season_id: int
    items: list[SubscriptionOrderItem]


class TeamRegistrationSchema(Schema):
    team_id: int
    event_id: int
    partial: bool = False


class PlayerRegistrationSchema(Schema):
    team_id: int
    event_id: int
    player_ids: list[int]
