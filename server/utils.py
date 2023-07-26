import uuid

import razorpay
from django.conf import settings

CLIENT = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_razorpay_order(amount, currency="INR", receipt=None, notes=None):
    if receipt is None:
        receipt = str(uuid.uuid4())[:8]

    data = {
        "amount": amount,
        "currency": currency,
        "receipt": receipt,
        "notes": notes,
    }
    response = CLIENT.order.create(data=data)
    response["key"] = settings.RAZORPAY_KEY_ID
    response["order_id"] = response["id"]
    return response


def verify_razorpay_payment(payment_info):
    try:
        return CLIENT.utility.verify_payment_signature(payment_info)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False


def verify_razorpay_webhook_payload(body, signature):
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    try:
        return CLIENT.utility.verify_webhook_signature(body, signature, secret)
    except razorpay.errors.SignatureVerificationError as e:
        print(e)
        return False


def mask_string(s):
    n = len(s)
    if n >= 8:
        return s[:2] + "x" * (n - 4) + s[-2:]
    elif n >= 6:
        return s[:1] + "x" * (n - 2) + s[-1:]
    else:
        return s[:1] + "x" * (n - 1)
