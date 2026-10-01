from ninja import Schema

from server.transaction.schema import RazorpayOrderSchema


class AddEntrySchema(Schema):
    player_id: int


class CheckoutSchema(Schema):
    """What the page showed: who was ready, and what paying for them cost."""

    expected_amount: int
    expected_ids: list[int]


class CheckoutOrderSchema(RazorpayOrderSchema):
    timeout: int  # seconds Razorpay keeps the window payable


class SwapSchema(Schema):
    out_player_id: int
    in_player_id: int
