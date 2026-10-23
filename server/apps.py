from collections.abc import Sequence
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from ninja import ModelSchema, Schema

# pydantic 1 (ninja 0.22) turned numbers into strings for `str` fields, and
# pydantic 2 refuses them: the frontend sends ids as numbers to str fields
# (a spirit score's mvp_id), and tabs opened before a deploy keep doing so.
# Set here, before Django imports any schema, so every schema inherits it.
for _base in (Schema, ModelSchema):
    _base.model_config["coerce_numbers_to_str"] = True


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

    def ready(self) -> None:
        from server.cache.invalidation import connect
        from server.mcp.redirects import fail_open

        connect()
        fail_open()
