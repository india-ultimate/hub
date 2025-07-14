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


class ServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "server"

    def ready(self) -> None:
        """Import signals when the app is ready"""
        import server.signals  # noqa: F401
