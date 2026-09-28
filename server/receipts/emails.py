"""A receipt or refund note, sent as the body of an email."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction as db_transaction
from django.utils.html import strip_tags

from server.receipts.models import Receipt
from server.receipts.render import render_html
from server.task.helpers import queue_emails

logger = logging.getLogger(__name__)


def queue_receipt_email(receipt: Receipt) -> None:
    """Emailed once the issuing transaction commits, so a rollback sends nothing.

    The email is drawn and built after the commit and `robust`, so a bug in
    it is logged and can never roll back the payment or refund that made the
    receipt.
    """
    db_transaction.on_commit(lambda: _send(receipt.pk), robust=True)


def _send(receipt_id: int) -> None:
    try:
        receipt = Receipt.objects.filter(pk=receipt_id).first()
        if receipt is None or "@" not in receipt.payer_email:
            return
        label = "Refund note" if receipt.kind == Receipt.Kind.REFUND else "Receipt"
        html = render_html(receipt, "email")
        message = EmailMultiAlternatives(
            subject=f"{label} {receipt.number} — India Ultimate",
            body=strip_tags(html),
            from_email=settings.EMAIL_HOST_USER,
            to=[receipt.payer_email],
        )
        message.attach_alternative(html, "text/html")
        queue_emails([message])
    except Exception:
        logger.exception("Email for receipt %s could not be sent", receipt_id)
        raise
