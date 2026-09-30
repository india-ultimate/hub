import datetime
import logging
import uuid
from typing import Any

import razorpay
from django.conf import settings
from django.utils.timezone import now

from server.payment_account.models import PaymentAccount, SecretsUnavailable

from ..models import RazorpayTransaction
from ..schema import RazorpayCallbackSchema

CLIENT = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

RAZORPAY_NOTES_MAX = 512
RAZORPAY_DESCRIPTION_MAX = 255

logger = logging.getLogger(__name__)


def client_for(account: PaymentAccount | None) -> razorpay.Client:
    """India Ultimate's client for None, else one with the account's own keys."""
    if account is None:
        return CLIENT
    return razorpay.Client(auth=(account.key_id, account.key_secret))


def create_order(
    amount: int,
    currency: str = "INR",
    receipt: str | None = None,
    notes: dict[str, Any] | None = None,
    account: PaymentAccount | None = None,
) -> dict[str, Any] | None:
    if receipt is None:
        receipt = str(uuid.uuid4())[:8]

    data = {
        "amount": amount,
        "currency": currency,
        "receipt": receipt,
        "notes": notes,
    }
    try:
        response = client_for(account).order.create(data=data)
    except Exception as e:
        logger.error("Failed to initiate Razorpay payment: %s", e)
        return None

    # Checkout must open on the account the order was placed on.
    response["key"] = account.key_id if account else settings.RAZORPAY_KEY_ID
    response["order_id"] = response["id"]
    return response


def _all_since(resource: Any, since: datetime.datetime | None) -> list[dict[str, Any]]:
    """Every page Razorpay has for this resource since `since`, or a week ago."""
    today = now()
    start = since if since is not None else today - datetime.timedelta(days=7)

    page_size = 100
    default = {
        "from": int(start.timestamp()),
        "to": int(today.timestamp()),
        "count": page_size,
    }

    items: list[dict[str, Any]] = []
    skip = 0
    while True:
        page = resource.all(dict(**default, skip=skip))
        if page["count"] == 0:
            break
        items.extend(page["items"])
        skip += page_size

    return items


def get_transactions(
    since: datetime.datetime | None = None, account: PaymentAccount | None = None
) -> list[dict[str, Any]]:
    return _all_since(client_for(account).payment, since)


def get_refunds(
    since: datetime.datetime | None = None, account: PaymentAccount | None = None
) -> list[dict[str, Any]]:
    return _all_since(client_for(account).refund, since)


def verify_payment(payment_info: dict[str, str], account: PaymentAccount | None = None) -> bool:
    # Razorpay signs order_id|payment_id with the key secret of the account
    # the order was placed on.
    try:
        return client_for(account).utility.verify_payment_signature(payment_info)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False
    except SecretsUnavailable as error:
        logger.error("Payment on %s can't be checked: %s", account, error)
        return False


def verify_webhook_payload(
    body: str, signature: str, account: PaymentAccount | None = None
) -> bool:
    try:
        secret = account.webhook_secret if account else settings.RAZORPAY_WEBHOOK_SECRET
    except SecretsUnavailable as error:
        logger.error("Webhook for %s can't be checked: %s", account, error)
        return False
    # A state's webhook without a secret yet accepts nothing, rather than
    # anything signed with an empty key.
    if account is not None and not secret:
        return False
    try:
        return CLIENT.utility.verify_webhook_signature(body, signature, secret)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False


def update_transaction(payment: RazorpayCallbackSchema) -> RazorpayTransaction | None:
    try:
        transaction = RazorpayTransaction.objects.get(order_id=payment.razorpay_order_id)
    except RazorpayTransaction.DoesNotExist:
        return None

    n = len("razorpay_")
    for key, value in payment.dict().items():
        field = key[n:]
        # The model field is payment_signature; writing "signature" silently
        # went nowhere, which is why every completed row has an empty one.
        setattr(transaction, "payment_signature" if field == "signature" else field, value)

    return mark_transaction_completed(transaction)


def mark_transaction_completed(transaction: RazorpayTransaction) -> RazorpayTransaction:
    # A refund is the last word on an order. Razorpay keeps reporting the
    # payment as captured afterwards, and the nightly sync used to march
    # refunded rows back to completed.
    if transaction.status == RazorpayTransaction.TransactionStatusChoices.REFUNDED:
        return transaction

    transaction.status = RazorpayTransaction.TransactionStatusChoices.COMPLETED
    transaction.save()

    return transaction
