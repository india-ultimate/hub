from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, register


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


class ServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "server"
