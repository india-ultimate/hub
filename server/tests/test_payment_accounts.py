"""Tournament fees paid into a state association's own Razorpay account."""

import datetime
import hashlib
import hmac
import json
from io import StringIO
from typing import Any
from unittest import mock

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from razorpay.resources.order import Order
from razorpay.resources.payment import Payment

from server.core.models import Team
from server.payment_account.models import PaymentAccount, SecretsUnavailable
from server.subscription.refunds import refund_order
from server.tests.base import ApiBaseTestCase, fake_id, make_account
from server.tests.test_subscription_model import make_player
from server.tournament.models import Event, Tournament
from server.transaction.models import RazorpayTransaction
from server.utils import today


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


TEAM_FEE = 500000
PLAYER_FEE = 100000
STATE_KEYS = ("rzp_test_state0000000001", "state-secret")


def open_event(**fields: Any) -> Event:
    day = today()
    defaults: dict[str, Any] = {
        "title": "KA State Open",
        "start_date": day + datetime.timedelta(days=20),
        "end_date": day + datetime.timedelta(days=22),
        "team_registration_start_date": day - datetime.timedelta(days=1),
        "team_registration_end_date": day + datetime.timedelta(days=10),
        "player_registration_start_date": day - datetime.timedelta(days=1),
        "player_registration_end_date": day + datetime.timedelta(days=10),
        "team_fee": TEAM_FEE,
        "partial_team_fee": 200000,
        "player_fee": PLAYER_FEE,
    }
    return Event.objects.create(**{**defaults, **fields})


def razorpay_order(amount: int) -> dict[str, Any]:
    """What Razorpay's order.create answers, before create_order adds to it."""
    return {
        "id": f"order_{fake_id(14)}",
        "entity": "order",
        "amount": amount,
        "currency": "INR",
        "receipt": "r",
        "status": "created",
        "notes": {},
    }


def signature(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


class RoutedTestCase(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()
        self.account = make_account()
        self.team = Team.objects.create(name="Payers")
        self.team.admins.add(self.user)
        self.event = open_event(payment_account=self.account)
        self.tournament = Tournament.objects.create(event=self.event)

    def place(self, data: dict[str, Any], amount: int = TEAM_FEE) -> tuple[Any, mock.MagicMock]:
        """Post an order, with Razorpay's order.create answered locally."""
        with mock.patch.object(
            Order, "create", autospec=True, return_value=razorpay_order(amount)
        ) as create:
            response = self.client.post(
                "/api/transactions/razorpay", data=data, content_type="application/json"
            )
        return response, create

    def callback(self, order_id: str, secret: str) -> Any:
        payment_id = f"pay_{fake_id(14)}"
        return self.client.post(
            "/api/transactions/razorpay/callback",
            data={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature(secret, f"{order_id}|{payment_id}"),
            },
            content_type="application/json",
        )


class TestRoutedOrders(RoutedTestCase):
    def test_a_team_fee_is_ordered_on_the_events_account(self) -> None:
        response, create = self.place({"team_id": self.team.id, "event_id": self.event.id})
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(STATE_KEYS, create.call_args.args[0].client.auth)
        body = response.json()
        self.assertEqual("rzp_test_state0000000001", body["key"])
        self.assertEqual("Karnataka Ultimate", body["name"])
        transaction = RazorpayTransaction.objects.get(order_id=body["order_id"])
        self.assertEqual(self.account, transaction.account)
        self.assertEqual(str(TEAM_FEE), transaction.notes["base_amount"])
        self.assertEqual("0", transaction.notes["penalty_amount"])

    def test_a_late_team_pays_its_penalty_into_the_states_account_too(self) -> None:
        day = today()
        late = open_event(
            title="Late Open",
            payment_account=self.account,
            team_registration_end_date=day - datetime.timedelta(days=2),
            team_late_penalty_end_date=day + datetime.timedelta(days=5),
            team_late_penalty=150000,
        )
        Tournament.objects.create(event=late)
        total = TEAM_FEE + 2 * 150000
        response, create = self.place({"team_id": self.team.id, "event_id": late.id}, total)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(STATE_KEYS, create.call_args.args[0].client.auth)
        self.assertEqual(total, create.call_args.kwargs["data"]["amount"])
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual(total, transaction.amount)
        self.assertEqual(
            {"base_amount": str(TEAM_FEE), "penalty_amount": "300000", "days_late": "2"},
            {k: transaction.notes[k] for k in ("base_amount", "penalty_amount", "days_late")},
        )

    def test_a_player_fee_is_ordered_on_the_events_account(self) -> None:
        self.tournament.teams.add(self.team)
        friend = make_player("friend@example.com")
        data = {"team_id": self.team.id, "event_id": self.event.id, "player_ids": [friend.id]}
        response, create = self.place(data, PLAYER_FEE)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(STATE_KEYS, create.call_args.args[0].client.auth)
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual(self.account, transaction.account)

    @override_settings(PAYMENT_ACCOUNT_ENCRYPTION_KEY="")
    def test_our_own_events_stay_on_our_account(self) -> None:
        # With the encryption key gone, too: our own orders never need it.
        ours = open_event(title="Nationals")
        Tournament.objects.create(event=ours)
        response, create = self.place({"team_id": self.team.id, "event_id": ours.id})
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            create.call_args.args[0].client.auth,
        )
        self.assertEqual(settings.APP_NAME, response.json()["name"])
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertIsNone(transaction.account)

    def test_an_inactive_account_takes_no_orders(self) -> None:
        self.account.is_active = False
        self.account.save()
        response, create = self.place({"team_id": self.team.id, "event_id": self.event.id})
        self.assertEqual(400, response.status_code)
        self.assertIn("aren't set up yet", response.json()["message"])
        create.assert_not_called()

    def test_an_unreadable_secret_takes_no_orders(self) -> None:
        with override_settings(PAYMENT_ACCOUNT_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            response, create = self.place({"team_id": self.team.id, "event_id": self.event.id})
        self.assertEqual(400, response.status_code)
        create.assert_not_called()
        self.assertFalse(RazorpayTransaction.objects.exists())


class TestRoutedCallback(RoutedTestCase):
    def order_id(self) -> str:
        response, _ = self.place({"team_id": self.team.id, "event_id": self.event.id})
        return str(response.json()["order_id"])

    def test_the_callback_is_checked_with_the_accounts_secret(self) -> None:
        order_id = self.order_id()
        response = self.callback(order_id, "state-secret")
        self.assertEqual(200, response.status_code, response.content)
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(RazorpayTransaction.TransactionStatusChoices.COMPLETED, transaction.status)
        self.assertIn(self.team, self.tournament.teams.all())

    def test_our_secret_does_not_pass_for_a_state_order(self) -> None:
        order_id = self.order_id()
        response = self.callback(order_id, settings.RAZORPAY_KEY_SECRET)
        self.assertEqual(422, response.status_code)
        self.assertEqual("created", RazorpayTransaction.objects.get(order_id=order_id).status)

    def test_a_rotated_encryption_key_leaves_the_order_unpaid(self) -> None:
        order_id = self.order_id()
        with override_settings(PAYMENT_ACCOUNT_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            response = self.callback(order_id, "state-secret")
        self.assertEqual(422, response.status_code)
        self.assertEqual("created", RazorpayTransaction.objects.get(order_id=order_id).status)

    def test_an_unknown_order_is_not_found(self) -> None:
        self.assertEqual(404, self.callback("order_nothere", "state-secret").status_code)


def unpaid_order(
    account: PaymentAccount | None, event: Event, team: Team, user: Any
) -> RazorpayTransaction:
    return RazorpayTransaction.objects.create(
        order_id=f"order_{fake_id(14)}",
        amount=TEAM_FEE,
        currency="INR",
        status="created",
        user=user,
        event=event,
        team=team,
        type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
        account=account,
    )


@override_settings(RAZORPAY_WEBHOOK_SECRET="our-hook")  # noqa: S106
class TestAccountWebhooks(RoutedTestCase):
    def deliver(self, url: str, order: RazorpayTransaction, secret: str) -> None:
        body = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {"entity": {"id": f"pay_{fake_id(14)}", "order_id": order.order_id}}
                },
            }
        )
        response = self.client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature(secret, body),
        )
        self.assertEqual(200, response.status_code, response.content)
        order.refresh_from_db()

    def test_a_states_webhook_settles_its_own_order(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/karnataka", order, "state-hook")
        self.assertEqual("completed", order.status)
        self.assertIn(self.team, self.tournament.teams.all())

    def test_an_inactive_accounts_webhook_still_settles(self) -> None:
        # Deactivated after the tournament: a late capture still counts.
        self.account.is_active = False
        self.account.save()
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/karnataka", order, "state-hook")
        self.assertEqual("completed", order.status)

    def test_a_states_webhook_cannot_settle_our_order(self) -> None:
        order = unpaid_order(None, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/karnataka", order, "state-hook")
        self.assertEqual("created", order.status)

    def test_our_secret_is_refused_on_a_states_url(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/karnataka", order, "our-hook")
        self.assertEqual("created", order.status)

    def test_our_url_cannot_settle_a_states_order(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook", order, "our-hook")
        self.assertEqual("created", order.status)

    def test_without_a_webhook_secret_nothing_is_accepted(self) -> None:
        self.account.webhook_secret = ""
        self.account.save()
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/karnataka", order, "")
        self.assertEqual("created", order.status)

    def test_an_unknown_slug_is_refused(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.deliver("/api/transactions/razorpay/webhook/nowhere", order, "state-hook")
        self.assertEqual("created", order.status)


SYNC = "server.management.commands.sync_razorpay_transactions"


def captured(order: RazorpayTransaction) -> dict[str, Any]:
    return {"id": f"pay_{fake_id(14)}", "order_id": order.order_id, "status": "captured"}


class TestAccountSync(RoutedTestCase):
    def sync(self, feeds: dict[str | None, Any]) -> str:
        """Run the sync with each account's payment feed answered locally."""

        def payments(since: Any = None, account: PaymentAccount | None = None) -> Any:
            feed = feeds.get(account.slug if account else None, [])
            if isinstance(feed, Exception):
                raise feed
            return feed

        self.errors = StringIO()
        with mock.patch(f"{SYNC}.get_transactions", side_effect=payments), mock.patch(
            f"{SYNC}.get_refunds", return_value=[]
        ):
            call_command(
                "sync_razorpay_transactions", "--no-email", stdout=StringIO(), stderr=self.errors
            )
        return self.errors.getvalue()

    def test_a_state_order_is_settled_from_the_states_feed(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.sync({"karnataka": [captured(order)]})
        order.refresh_from_db()
        self.assertEqual("completed", order.status)
        self.assertIn(self.team, self.tournament.teams.all())

    def test_our_feed_does_not_touch_a_state_order(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.sync({None: [captured(order)]})
        order.refresh_from_db()
        self.assertEqual("created", order.status)

    def test_one_broken_account_does_not_stop_the_others(self) -> None:
        other = make_account(slug="goa", name="Goa Ultimate")
        order = unpaid_order(other, self.event, self.team, self.user)
        # Cron sees the failure; the other accounts were still synced.
        with self.assertRaisesMessage(CommandError, "Not synced: Karnataka Ultimate"):
            self.sync({"karnataka": RuntimeError("bad key"), "goa": [captured(order)]})
        order.refresh_from_db()
        self.assertEqual("completed", order.status)
        self.assertIn("Karnataka Ultimate was not synced", self.errors.getvalue())

    def test_our_broken_account_does_not_stop_the_states(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        with self.assertRaisesMessage(CommandError, "Not synced: India Ultimate"):
            self.sync({None: RuntimeError("bad key"), "karnataka": [captured(order)]})
        order.refresh_from_db()
        self.assertEqual("completed", order.status)
        self.assertIn("India Ultimate was not synced", self.errors.getvalue())

    def test_an_inactive_account_is_still_synced(self) -> None:
        # Inactive only stops new orders: a payment captured before, or a
        # dashboard refund after, must still reach the Hub.
        self.account.is_active = False
        self.account.save()
        order = unpaid_order(self.account, self.event, self.team, self.user)
        self.sync({"karnataka": [captured(order)]})
        order.refresh_from_db()
        self.assertEqual("completed", order.status)


class TestAccountRefunds(RoutedTestCase):
    def test_a_staff_refund_goes_through_the_orders_account(self) -> None:
        order = unpaid_order(self.account, self.event, self.team, self.user)
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            status="completed", payment_id="pay_state0000000001"
        )
        order.refresh_from_db()
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_x1", "status": "processed"}
        ) as refund:
            refund_order(order, by=self.user, reason="Team withdrew")
        self.assertEqual(STATE_KEYS, refund.call_args.args[0].client.auth)
        self.assertEqual("pay_state0000000001", refund.call_args.args[1])
        order.refresh_from_db()
        self.assertEqual("refunded", order.status)
