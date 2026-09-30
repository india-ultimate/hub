"""A Razorpay account other than India Ultimate's, that a tournament's fees go to."""

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import QuerySet

from server.core.models import User

if TYPE_CHECKING:
    from cryptography.fernet import Fernet


class SecretsUnavailable(Exception):  # noqa: N818
    """An account's secrets can't be read: the encryption key is missing or wrong."""


def _fernet() -> "Fernet":
    # Imported here, not at module scope: every worker loads models at startup.
    from cryptography.fernet import Fernet

    key = settings.PAYMENT_ACCOUNT_ENCRYPTION_KEY
    if not key:
        raise SecretsUnavailable("PAYMENT_ACCOUNT_ENCRYPTION_KEY is not set.")
    try:
        return Fernet(key)
    except ValueError as error:
        raise SecretsUnavailable("PAYMENT_ACCOUNT_ENCRYPTION_KEY is not a Fernet key.") from error


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    from cryptography.fernet import InvalidToken  # see _fernet()

    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as error:
        raise SecretsUnavailable("Encrypted with a different key.") from error


class PaymentAccount(models.Model):
    name = models.CharField(
        max_length=255, help_text="Shown to payers at checkout and to the account's viewers."
    )
    slug = models.SlugField(unique=True, help_text="Used in the webhook URL and the page URL.")
    key_id = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                r"^rzp_(test|live)_\w+$", "A Razorpay key ID starts with rzp_test_ or rzp_live_."
            )
        ],
    )
    # Fernet tokens. Read and write them through key_secret and webhook_secret.
    key_secret_encrypted = models.TextField(editable=False)
    webhook_secret_encrypted = models.TextField(editable=False, blank=True)
    viewers = models.ManyToManyField(
        User,
        related_name="viewable_payment_accounts",
        blank=True,
        help_text="People from the association who may see its payments in the Hub.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="An inactive account takes no new orders but is still synced. "
        "Its viewers still see its payments.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    @property
    def is_test_mode(self) -> bool:
        return self.key_id.startswith("rzp_test_")

    @property
    def keys_match_environment(self) -> bool:
        """Test keys on a test server, live keys on a live one.

        A test-card "payment" on a live Hub would roster a team with no money
        moved. A server with no Razorpay key counts as a test server, so tests
        run without one stay deterministic.
        """
        ours = settings.RAZORPAY_KEY_ID
        return self.is_test_mode == (not ours or ours.startswith("rzp_test_"))

    @property
    def key_secret(self) -> str:
        return decrypt(self.key_secret_encrypted)

    @key_secret.setter
    def key_secret(self, value: str) -> None:
        self.key_secret_encrypted = encrypt(value)

    @property
    def webhook_secret(self) -> str:
        return decrypt(self.webhook_secret_encrypted)

    @webhook_secret.setter
    def webhook_secret(self, value: str) -> None:
        self.webhook_secret_encrypted = encrypt(value)

    def is_ready(self) -> bool:
        """Whether orders can be taken: active, in this server's mode, with a
        secret this server can read."""
        if not self.is_active or not self.keys_match_environment:
            return False
        try:
            return bool(self.key_secret)
        except SecretsUnavailable:
            return False


def viewable_by(user: User) -> QuerySet[PaymentAccount]:
    """Staff see every account; anyone else only those they were made a viewer of."""
    accounts = PaymentAccount.objects.order_by("name")
    return accounts if user.is_staff else accounts.filter(viewers=user)
