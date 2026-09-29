from collections.abc import Sequence
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def enforce_otp_email_hash(app_configs: Any, **kwargs: Any) -> list[Error]:
    errors = []
    if not settings.OTP_EMAIL_HASH_KEY:
        errors.append(
            Error(
                "OTP_EMAIL_HASH_KEY needs to be set",
                hint="Set the environment variable to be non-empty.",
                obj=settings,
                id="server.E001",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_phonepe_env_vars(app_configs: Any, **kwargs: Any) -> Sequence[Error | Warning]:
    errors = []
    if not settings.PHONEPE_MERCHANT_ID:
        return [Warning("PHONEPE_MERCHANT_ID not set", id="settings.W001", obj=settings)]
    if settings.PHONEPE_PRODUCTION and settings.PHONEPE_MERCHANT_ID.endswith("UAT"):
        errors.append(
            Error(
                "Use production PhonePe MERCHANT_ID",
                hint="Set the correct values for PHONEPE_MERCHANT_ID and PHONEPE_PRODUCTION.",
                obj=settings,
                id="server.E002",
            )
        )
    elif not settings.PHONEPE_PRODUCTION and not settings.PHONEPE_MERCHANT_ID.endswith("UAT"):
        errors.append(
            Error(
                "Use UAT PhonePe MERCHANT_ID",
                hint="Set the correct values for PHONEPE_MERCHANT_ID and PHONEPE_PRODUCTION.",
                obj=settings,
                id="server.E003",
            )
        )

    return errors


@register(Tags.security, deploy=True)
def check_receipt_tax_ids(app_configs: Any, **kwargs: Any) -> Sequence[Warning]:
    # Not an Error: a missing line is better than refusing to boot. But every
    # receipt is a tax document, so the deploy log has to say it.
    missing = [name for name in ("gstin", "pan") if not settings.RECEIPT_ISSUER.get(name)]
    if missing:
        return [
            Warning(
                f"Receipts will carry no tax line: {', '.join(missing).upper()} not set",
                hint="Set RECEIPT_ISSUER_GSTIN and RECEIPT_ISSUER_PAN.",
                obj=settings,
                id="settings.W002",
            )
        ]
    return []


class ServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "server"
