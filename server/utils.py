import datetime
import uuid
from typing import Any

import razorpay
from django.conf import settings
from django.utils.timezone import now
from requests.exceptions import RequestException

CLIENT = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

RAZORPAY_NOTES_MAX = 512
RAZORPAY_DESCRIPTION_MAX = 255


def create_razorpay_order(
    amount: int,
    currency: str = "INR",
    receipt: str | None = None,
    notes: dict[str, Any] | None = None,
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
        response = CLIENT.order.create(data=data)
    except (RequestException, razorpay.errors.BadRequestError) as e:
        print(f"ERROR: Failed to connect to Razorpay with {e}")
        return None

    response["key"] = settings.RAZORPAY_KEY_ID
    response["order_id"] = response["id"]
    return response


def get_transactions() -> list[dict[str, Any]]:
    today = now()
    last_week = today - datetime.timedelta(days=7)

    page_size = 100
    default = {
        "from": int(last_week.timestamp()),
        "to": int(today.timestamp()),
        "count": page_size,
    }

    transactions = []
    skip = 0
    while True:
        query = dict(**default, skip=skip)
        transactions_ = CLIENT.payment.all(query)
        if transactions_["count"] == 0:
            break
        else:
            transactions.extend(transactions_["items"])
        skip += page_size

    return transactions


def verify_razorpay_payment(payment_info: dict[str, str]) -> bool:
    try:
        return CLIENT.utility.verify_payment_signature(payment_info)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False


def verify_razorpay_webhook_payload(body: str, signature: str) -> bool:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    try:
        return CLIENT.utility.verify_webhook_signature(body, signature, secret)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False


def mask_string(s: str) -> str:
    n = len(s)
    long_str = 8
    medium_str = 6
    if n >= long_str:
        return s[:2] + "x" * (n - 4) + s[-2:]
    elif n >= medium_str:
        return s[:1] + "x" * (n - 2) + s[-1:]
    else:
        return s[:1] + "x" * (n - 1)
