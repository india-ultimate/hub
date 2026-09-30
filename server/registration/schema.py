from ninja import Schema


class AddEntrySchema(Schema):
    player_id: int


class CheckoutSchema(Schema):
    expected_amount: int
