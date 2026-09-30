"""Tournament fees paid into a state association's own Razorpay account."""

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings

from server.payment_account.models import SecretsUnavailable
from server.tests.base import make_account


class TestPaymentAccountSecrets(TestCase):
    def test_secrets_are_encrypted_at_rest(self) -> None:
        account = make_account()
        account.refresh_from_db()
        self.assertNotIn("state-secret", account.key_secret_encrypted)
        self.assertNotIn("state-hook", account.webhook_secret_encrypted)
        self.assertEqual("state-secret", account.key_secret)
        self.assertEqual("state-hook", account.webhook_secret)

    def test_another_key_cannot_read_them(self) -> None:
        account = make_account()
        with override_settings(PAYMENT_ACCOUNT_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(SecretsUnavailable):
                _ = account.key_secret
            self.assertFalse(account.is_ready())

    def test_no_key_cannot_read_them(self) -> None:
        account = make_account()
        with override_settings(PAYMENT_ACCOUNT_ENCRYPTION_KEY=""), self.assertRaises(
            SecretsUnavailable
        ):
            _ = account.key_secret

    def test_a_blank_webhook_secret_stays_blank(self) -> None:
        self.assertEqual("", make_account(webhook_secret="").webhook_secret)

    def test_mode_follows_the_key(self) -> None:
        self.assertTrue(make_account().is_test_mode)
        self.assertFalse(make_account(slug="live", key_id="rzp_live_abc").is_test_mode)

    @override_settings(RAZORPAY_KEY_ID="rzp_live_ours")
    def test_a_live_server_takes_no_orders_on_test_keys(self) -> None:
        self.assertFalse(make_account().is_ready())
        self.assertTrue(make_account(slug="live", key_id="rzp_live_abc").is_ready())

    @override_settings(RAZORPAY_KEY_ID="rzp_test_ours")
    def test_a_test_server_takes_no_orders_on_live_keys(self) -> None:
        self.assertFalse(make_account(slug="live", key_id="rzp_live_abc").is_ready())
        self.assertTrue(make_account().is_ready())
        with override_settings(RAZORPAY_KEY_ID=""):  # no keys configured: a test server
            self.assertTrue(make_account(slug="blank").is_ready())

    def test_only_an_active_account_is_ready(self) -> None:
        self.assertTrue(make_account().is_ready())
        self.assertFalse(make_account(slug="off", is_active=False).is_ready())
