import hashlib
import uuid
from typing import Any

from django.conf import settings
from phonepe.sdk.pg.env import Env
from phonepe.sdk.pg.payments.v1.models.request.pg_pay_request import PgPayRequest
from phonepe.sdk.pg.payments.v1.payment_client import PhonePePaymentClient

from server.models import User

phonepe_client = PhonePePaymentClient(
    settings.PHONEPE_MERCHANT_ID,
    settings.PHONEPE_SALT_KEY,
    settings.PHONEPE_SALT_INDEX,
    Env.UAT,
    should_publish_events=False,  # NOTE: not sure what this does
)


def initiate_payment(amount: int, user: User, host: str, next_url: str) -> dict[str, Any] | None:
    merchant_transaction_id = str(uuid.uuid4())
    ui_redirect_url = f"{host}/phonepe-transaction/{merchant_transaction_id}?next={next_url}"
    s2s_callback_url = f"{host}/api/phonepe-server"
    merchant_user_id = hashlib.md5(user.email.encode("utf8")).hexdigest()  # noqa: S324
    pay_page_request = PgPayRequest.pay_page_pay_request_builder(
        merchant_transaction_id=merchant_transaction_id,
        amount=amount,
        merchant_user_id=merchant_user_id,
        callback_url=s2s_callback_url,
        redirect_url=ui_redirect_url,
    )
    try:
        response = phonepe_client.pay(pay_page_request)
    except Exception:
        return None
    if not response.success:
        return None
    redirect_url = response.data.instrument_response.redirect_info.url
    return {
        "redirect_url": redirect_url,
        "transaction_id": merchant_transaction_id,
        "amount": amount,
    }
