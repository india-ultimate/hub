import io
import json
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from ninja import File, Router, UploadedFile

from server.core.models import Player
from server.lib.manual_transactions import validate_manual_transactions
from server.receipts.models import Receipt
from server.schema import (
    PlayerSchema,
    Response,
    ValidationStatsSchema,
)
from server.types import message_response

from .client import razorpay
from .models import (
    AuthenticatedHttpRequest,
    ManualTransaction,
    PaymentGateway,
    RazorpayTransaction,
)
from .schema import (
    ManualTransactionSchema,
    ManualTransactionValidationFormSchema,
    PhonePeTransactionSchema,
    PlayerRegistrationSchema,
    RazorpayCallbackSchema,
    RazorpayOrderSchema,
    RazorpayTransactionSchema,
    SubscriptionOrderSchema,
    TeamRegistrationSchema,
)
from .utils import (
    apply_transaction,
    create_transaction,
    list_transactions_by_type,
)

router = Router()


# Create Transaction APIs ####################


# Razorpay Transaction
@router.post(
    "/razorpay",
    response={200: RazorpayOrderSchema, 400: Response, 401: Response, 422: Response, 502: str},
)
def create_razorpay_transaction(
    request: AuthenticatedHttpRequest,
    order: SubscriptionOrderSchema | PlayerRegistrationSchema | TeamRegistrationSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order)


# Callback APIs ####################


@router.post(
    "/razorpay/callback", response={200: list[PlayerSchema], 502: str, 404: Response, 422: Response}
)
def handle_razorpay_callback(
    request: AuthenticatedHttpRequest, payment: RazorpayCallbackSchema
) -> tuple[int, QuerySet[Player] | message_response | str]:
    # The order first: its account's secret is what the signature is made with.
    existing = (
        RazorpayTransaction.objects.select_related("account")
        .filter(order_id=payment.razorpay_order_id)
        .first()
    )
    if existing is None:
        return 404, {"message": "No order found."}
    if not razorpay.verify_payment(payment.dict(), existing.account):
        return 422, {"message": "We were unable to ascertain the authenticity of the payment."}
    # The same guard the webhook has. A double-clicked or replayed callback
    # must not run the handlers again: subscription fulfilment is idempotent,
    # but nothing promises the registration handlers are.
    if existing.status in RazorpayTransaction.SETTLED:
        return 200, existing.players.all()

    transaction = razorpay.update_transaction(payment)
    if not transaction:
        return 404, {"message": "No order found."}

    apply_transaction(transaction)

    return 200, transaction.players.all()


# Webhook APIs ####################


@router.post("/razorpay/webhook", auth=None, response={200: Response})
@csrf_exempt
def payment_webhook(request: HttpRequest) -> message_response:
    body = request.body.decode("utf8")
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not razorpay.verify_webhook_payload(body, signature):
        return {"message": "Signature could not be verified"}

    data = json.loads(body)
    # Only money actually taken means anything here. Razorpay sends a dozen
    # other events to the same URL, and an authorized-but-not-captured
    # payment is not one we may act on. Both of these carry the captured
    # payment, and which one the dashboard subscribes to isn't recorded here.
    if data.get("event") not in ("payment.captured", "order.paid"):
        return {"message": "Ignored webhook"}
    entity = data["payload"]["payment"]["entity"]

    transaction = RazorpayTransaction.objects.filter(order_id=entity["order_id"]).first()
    if transaction is None:
        return {"message": "No order found."}
    # Razorpay retries a webhook until it sees a 200, and the callback has
    # usually landed first. A settled order is not touched again.
    if transaction.status in RazorpayTransaction.SETTLED:
        return {"message": "Already processed"}

    payment = RazorpayCallbackSchema(
        razorpay_payment_id=entity["id"],
        razorpay_order_id=entity["order_id"],
        razorpay_signature=f"webhook_{signature}",
    )
    updated = razorpay.update_transaction(payment)
    if updated is None:
        return {"message": "No order found."}

    apply_transaction(updated)

    return {"message": "Webhook processed"}


# Get Transaction APIs ####################


@router.get("/", response={200: list[dict[str, Any]]})
def list_transactions(
    request: AuthenticatedHttpRequest,
    user_only: bool = True,
    only_invalid: bool = False,
    only_manual: bool = False,
) -> list[dict[str, Any]]:
    user = request.user
    payment_type_schema_map = {
        PaymentGateway.MANUAL: ManualTransactionSchema,
        PaymentGateway.RAZORPAY: RazorpayTransactionSchema,
        PaymentGateway.PHONEPE: PhonePeTransactionSchema,
    }
    response_data = []
    for payment_type, schema in payment_type_schema_map.items():
        if only_manual and payment_type != PaymentGateway.MANUAL:
            continue
        transactions = list_transactions_by_type(user, payment_type, user_only, only_invalid)
        transaction_dicts = [schema.from_orm(t).dict() for t in transactions]
        receipts: dict[str, tuple[int, str]] = {}
        if payment_type == PaymentGateway.RAZORPAY:
            receipts = {
                order_id: (pk, number)
                for order_id, pk, number in Receipt.objects.filter(
                    kind=Receipt.Kind.RECEIPT,
                    transaction_id__in=[d["order_id"] for d in transaction_dicts],
                ).values_list("transaction_id", "id", "number")
            }
        for d in transaction_dicts:
            d["type"] = payment_type.value
            if "payment_date" not in d:
                d["payment_date"] = d["transaction_date"]
            d["receipt_id"], d["receipt_number"] = receipts.get(d.get("order_id", ""), (None, None))

        response_data.extend(transaction_dicts)
    return response_data


# Validate Transaction APIs ####################


@router.post("/bulk-validate", response={200: ValidationStatsSchema, 400: Response, 401: Response})
def validate_transactions(
    request: AuthenticatedHttpRequest,
    bank_statement: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, message_response] | tuple[int, dict[str, int]]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can validate transactions"}

    if not bank_statement.name or not bank_statement.name.endswith(".csv"):
        return 400, {"message": "Please upload a CSV file!"}

    text = bank_statement.read().decode("utf-8")
    stats = validate_manual_transactions(io.StringIO(text))
    return 200, stats


@router.post("/validate", response={200: ManualTransactionSchema, 400: Response, 401: Response})
def validate_transaction(
    request: AuthenticatedHttpRequest, data: ManualTransactionValidationFormSchema
) -> tuple[int, message_response] | tuple[int, ManualTransaction]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can validate transactions"}

    try:
        transaction = ManualTransaction.objects.get(transaction_id=data.transaction_id)
    except Player.DoesNotExist:
        return 400, {"message": "Transaction does not exist"}

    transaction.validation_comment = data.validation_comment
    transaction.validated = True
    transaction.save(update_fields=["validation_comment", "validated"])
    return 200, transaction
