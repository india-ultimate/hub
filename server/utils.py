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
    return CLIENT.utility.verify_payment_signature(payment_info)
