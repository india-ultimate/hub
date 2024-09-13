import io
import json
from base64 import b64decode
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from ninja import File, Router, UploadedFile

from server.core.models import Player
from server.lib.manual_transactions import validate_manual_transactions
from server.schema import (
    PlayerSchema,
    Response,
    ValidationStatsSchema,
)
from server.types import message_response

from .client import phonepe, razorpay
from .models import (
    AuthenticatedHttpRequest,
    ManualTransaction,
    PaymentGateway,
    PhonePeTransaction,
    RazorpayTransaction,
)
from .schema import (
    AnnualMembershipSchema,
    EventMembershipSchema,
    GroupMembershipSchema,
    ManualTransactionLiteSchema,
    ManualTransactionSchema,
    ManualTransactionValidationFormSchema,
    PhonePeOrderSchema,
    PhonePeTransactionSchema,
    PlayerRegistrationSchema,
    RazorpayCallbackSchema,
    RazorpayOrderSchema,
    RazorpayTransactionSchema,
    TeamRegistrationSchema,
)
from .utils import (
    create_transaction,
    list_transactions_by_type,
    update_transaction_player_memberships,
    update_transaction_player_registrations,
    update_transaction_team_registration,
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
    order: AnnualMembershipSchema
    | EventMembershipSchema
    | GroupMembershipSchema
    | TeamRegistrationSchema
    | PlayerRegistrationSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.RAZORPAY)


# Phonepe Transaction
@router.post(
    "/phonepe",
    response={200: PhonePeOrderSchema, 400: Response, 422: Response, 502: str},
)
def create_phonepe_transaction(
    request: AuthenticatedHttpRequest,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.PHONEPE)


# Manual Transaction
@router.post(
    "/manual/{transaction_id}",
    response={200: ManualTransactionLiteSchema, 400: Response, 422: Response, 502: str},
)
def create_manual_transaction(
    request: AuthenticatedHttpRequest,
    transaction_id: str,
    order: AnnualMembershipSchema | EventMembershipSchema | GroupMembershipSchema,
) -> tuple[int, str | message_response | dict[str, Any]]:
    return create_transaction(request, order, PaymentGateway.MANUAL, transaction_id)


# Callback APIs ####################


@router.post(
    "/razorpay/callback", response={200: list[PlayerSchema], 502: str, 404: Response, 422: Response}
)
def handle_razorpay_callback(
    request: AuthenticatedHttpRequest, payment: RazorpayCallbackSchema
) -> tuple[int, QuerySet[Player] | message_response | str]:
    authentic = razorpay.verify_payment(payment.dict())
    if not authentic:
        return 422, {"message": "We were unable to ascertain the authenticity of the payment."}

    transaction = razorpay.update_transaction(payment)
    if not transaction:
        return 404, {"message": "No order found."}

    if transaction.type == RazorpayTransaction.TransactionTypeChoices.ANNUAL_MEMBERSHIP:
        update_transaction_player_memberships(transaction)
    elif transaction.type == RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION:
        update_transaction_team_registration(transaction)
    elif transaction.type == RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION:
        update_transaction_player_registrations(transaction)

    return 200, transaction.players.all()


@router.get(
    "/phonepe/{transaction_id}",
    response={200: PhonePeTransactionSchema, 400: Response, 422: Response, 502: str},
)
def get_phonepe_transaction(
    request: AuthenticatedHttpRequest,
    transaction_id: str,
) -> tuple[int, message_response | PhonePeTransaction]:
    try:
        transaction = PhonePeTransaction.objects.get(transaction_id=transaction_id)
    except PhonePeTransaction.DoesNotExist:
        return 422, {"message": "PhonePe Transaction does not exist!"}

    # Check transaction status with PhonePe for pending transactions
    if transaction.status == PhonePeTransaction.TransactionStatusChoices.PENDING:
        transaction = phonepe.check_and_update_transaction(transaction)

        if transaction.status == PhonePeTransaction.TransactionStatusChoices.SUCCESS:
            update_transaction_player_memberships(transaction)

    return 200, transaction


@router.post("/phonepe/callback", auth=None, response={200: Response})
@csrf_exempt
def phonepe_callback(request: HttpRequest) -> message_response:
    body = request.body.decode("utf8")
    signature = request.headers.get("X-Verify", "")
    if not phonepe.verify_callback_checksum(body, signature):
        return {"message": "Signature could not be verified"}

    encoded_data = json.loads(body)["response"]
    data = json.loads(b64decode(encoded_data).decode("utf8"))
    code = data["code"]
    prefix = "PAYMENT_"
    if not code.startswith(prefix):
        return {"message": "Ignored webhook"}
    code = code[len(prefix) :]
    transaction_id = data["data"]["merchantTransactionId"]
    try:
        transaction = PhonePeTransaction.objects.get(transaction_id=transaction_id)
    except PhonePeTransaction.DoesNotExist:
        return {"message": "Transaction not found"}
    phonepe.update_transaction(transaction, code)
    return {"message": "Webhook processed"}


# Webhook APIs ####################


@router.post("/razorpay/webhook", auth=None, response={200: Response})
@csrf_exempt
def payment_webhook(request: HttpRequest) -> message_response:
    body = request.body.decode("utf8")
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not razorpay.verify_webhook_payload(body, signature):
        return {"message": "Signature could not be verified"}
    data = json.loads(body)["payload"]["payment"]["entity"]
    payment = RazorpayCallbackSchema(
        razorpay_payment_id=data["id"],
        razorpay_order_id=data["order_id"],
        razorpay_signature=f"webhook_{signature}",
    )
    transaction = razorpay.update_transaction(payment)
    if not transaction:
        return {"message": "No order found."}

    if transaction.type == RazorpayTransaction.TransactionTypeChoices.ANNUAL_MEMBERSHIP:
        update_transaction_player_memberships(transaction)
    elif transaction.type == RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION:
        update_transaction_team_registration(transaction)
    elif transaction.type == RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION:
        update_transaction_player_registrations(transaction)

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
        for d in transaction_dicts:
            d["type"] = payment_type.value
            if "payment_date" not in d:
                d["payment_date"] = d["transaction_date"]

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
