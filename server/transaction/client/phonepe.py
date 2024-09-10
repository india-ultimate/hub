import hashlib
import logging
import uuid
from typing import Any

from django.conf import settings
from phonepe.sdk.pg.env import Env
from phonepe.sdk.pg.payments.v1.models.request.pg_pay_request import PgPayRequest
from phonepe.sdk.pg.payments.v1.payment_client import PhonePePaymentClient

from server.core.models import User

from ..models import PhonePeTransaction

env = Env.UAT if not settings.PHONEPE_PRODUCTION else Env.PROD
phonepe_client = PhonePePaymentClient(
    settings.PHONEPE_MERCHANT_ID,
    settings.PHONEPE_SALT_KEY,
    settings.PHONEPE_SALT_INDEX,
    env,
    should_publish_events=False,  # NOTE: not sure what this does
)
logger = logging.getLogger(__name__)


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
    except Exception as e:
        logger.error("Failed to initiate PhonePe payment: %s", e)
        return None
    if not response.success:
        return None
    redirect_url = response.data.instrument_response.redirect_info.url
    return {
        "redirect_url": redirect_url,
        "transaction_id": merchant_transaction_id,
        "amount": amount,
    }


def verify_callback_checksum(body: str, signature: str) -> bool:
    return phonepe_client.verify_response(x_verify=signature, response=body)


def check_transaction_status(transaction_id: str) -> dict[str, Any]:
    response = phonepe_client.check_status(transaction_id)
    return response.to_dict()


def check_and_update_transaction(transaction: PhonePeTransaction) -> PhonePeTransaction:
    data = check_transaction_status(str(transaction.transaction_id))
    code = data["code"]
    prefix = "PAYMENT_"
    if code.startswith(prefix):
        code = code[len(prefix) :]
        if transaction.status != code.lower():
            return update_transaction(transaction, code)
    return transaction


def update_transaction(transaction: PhonePeTransaction, status_code: str) -> PhonePeTransaction:
    transaction.status = getattr(PhonePeTransaction.TransactionStatusChoices, status_code)
    transaction.save(update_fields=["status"])
    return transaction
