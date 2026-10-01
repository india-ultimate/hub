"""A state's tournament fees, paid into its own Razorpay test account.

Every payment goes through the real Razorpay test checkout with the state's
test keys, and is then looked up at Razorpay to prove whose account it is
in. Skipped unless both India Ultimate's key and the state's are test keys.
"""

import datetime
import hashlib
import hmac
import json
import os
import uuid
from contextlib import ExitStack

import pytest
import razorpay
from django.core.management import call_command
from django.test import Client
from seleniumbase import BaseCase

from server.core.models import Player, Team, User
from server.tests import test_subscription_integration as subscription_flows
from server.tests import test_ui
from server.tests.base import make_account
from server.tests.localserver import APP_URL, running_test_server
from server.tests.razorpay_checkout import complete_razorpay_test_payment
from server.tournament.models import Event, Registration, Tournament
from server.transaction.client.razorpay import client_for
from server.transaction.models import RazorpayRefund, RazorpayTransaction
from server.utils import today

STATE_KEY_ID = os.environ.get("STATE_RAZORPAY_KEY_ID", "")
STATE_KEY_SECRET = os.environ.get("STATE_RAZORPAY_KEY_SECRET", "")
TEAM_FEE = 100000  # ₹1,000
PARTIAL_FEE = 40000
PLAYER_FEE = 20000
COMPLETED = RazorpayTransaction.TransactionStatusChoices.COMPLETED


@pytest.mark.skipif(
    not (
        STATE_KEY_ID.startswith("rzp_test_")
        and os.environ.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_")
    ),
    reason="needs Razorpay test keys for India Ultimate and for the state",
)
@pytest.mark.django_db(transaction=True)
class TestPaymentAccountIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as
    admin_sign_in = test_ui.TestIntegration.admin_sign_in
    refund_in_admin = subscription_flows.TestSubscriptionIntegration.refund_in_admin

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        self.account = make_account(
            "test-state",
            name="Test State Association",
            key_id=STATE_KEY_ID,
            key_secret=STATE_KEY_SECRET,
            webhook_secret=uuid.uuid4().hex,
        )
        self.state = client_for(self.account)
        self.ours = client_for(None)
        day = today()
        self.event = Event.objects.create(
            title=f"State Open {uuid.uuid4().hex[:6]}",
            start_date=day + datetime.timedelta(days=20),
            end_date=day + datetime.timedelta(days=22),
            team_registration_start_date=day - datetime.timedelta(days=1),
            team_registration_end_date=day + datetime.timedelta(days=10),
            team_partial_registration_end_date=day + datetime.timedelta(days=5),
            player_registration_start_date=day - datetime.timedelta(days=1),
            player_registration_end_date=day + datetime.timedelta(days=10),
            team_fee=TEAM_FEE,
            partial_team_fee=PARTIAL_FEE,
            player_fee=PLAYER_FEE,
            payment_account=self.account,
        )
        self.tournament = Tournament.objects.create(event=self.event)
        self.captain = User.objects.create_user(
            "captain@example.com", "captain@example.com", "pw", first_name="Asha", last_name="K"
        )
        Player.objects.create(user=self.captain, date_of_birth=datetime.date(1995, 1, 1))
        self.team = Team.objects.create(name="State Testers")
        self.team.admins.add(self.captain)

    # Helpers ####################

    def latest(self, kind: str) -> RazorpayTransaction:
        return RazorpayTransaction.objects.filter(type=kind).latest("payment_date")

    def assert_in_states_account(self, order: RazorpayTransaction) -> None:
        self.assertEqual(self.account, order.account)
        self.assertEqual(COMPLETED, order.status)
        payment = self.state.payment.fetch(order.payment_id)
        self.assertEqual("captured", payment["status"])
        self.assertEqual(order.amount, payment["amount"])
        self.assertEqual(order.order_id, payment["order_id"])
        # Our keys can't see it: it is not in our account at all.
        with self.assertRaises(razorpay.errors.BadRequestError):
            self.ours.order.fetch(order.order_id)

    def pay_team(self, button: str) -> RazorpayTransaction:
        """Pay the team fee from the team's registration page."""
        partial = button.startswith("Pay partial")
        self.sign_in_as(self.captain)
        self.open(f"{APP_URL}/tournament/{self.event.slug}/team/{self.team.slug}/registration")
        self.assert_text(self.team.name, "h1")
        complete_razorpay_test_payment(self, f'button:contains("{button}")')
        if partial:
            self.assert_text("Part of the team fee paid.", timeout=150)
        else:
            self.assert_text("Team fee paid.", timeout=150)
            self.assert_text("Paid to Test State Association", timeout=30)
        return self.latest(
            RazorpayTransaction.TransactionTypeChoices.PARTIAL_TEAM_REGISTRATION
            if partial
            else RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION
        )

    # Flows ####################

    def test_a_team_fee_lands_in_the_states_account(self) -> None:
        order = self.pay_team("Pay ₹1,000")
        self.assert_in_states_account(order)
        self.assertIn(self.team, self.tournament.teams.all())

    def test_partial_then_the_rest_both_land_in_the_states_account(self) -> None:
        partial = self.pay_team("Pay partial ₹400")
        self.assert_in_states_account(partial)
        # A part-paid team is offered the rest.
        rest = self.pay_team("Pay ₹600")
        self.assert_in_states_account(rest)
        self.assertIn(self.team, self.tournament.teams.all())

    def test_a_player_fee_lands_in_the_states_account(self) -> None:
        self.tournament.teams.add(self.team)
        friend = test_ui.make_player("friend@example.com", first="Ravi", last="M")
        self.sign_in_as(self.captain)
        self.open(f"{APP_URL}/tournament/{self.event.slug}/team/{self.team.slug}/registration")
        self.assert_text(self.team.name, "h1")
        # With a fee, adding them readies them for the one checkout.
        dialog = '//dialog[@aria-label="Add players"]'
        self.click('button:contains("+ Add players")')
        self.type("#add-players-search", "Ravi")
        self.click(f'{dialog}//button[@aria-label="Add Ravi M"]')
        self.assert_text("✓ Added", dialog)
        self.click(f'{dialog}//button[normalize-space()="Done"]')
        ravi = '//ul[@aria-label="Not paid yet"]/li[contains(., "Ravi M")]'
        self.assert_text("Ready to pay", ravi, timeout=30)
        complete_razorpay_test_payment(self, 'button:contains("Pay ₹200")')
        self.assert_text("Payment received — 1 player rostered.", timeout=150)
        self.assert_element(
            '//ul[@aria-label="Rostered and paid"]/li[contains(., "Ravi M")]', timeout=30
        )
        order = self.latest(RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION)
        self.assert_in_states_account(order)
        self.assertIn(friend.player_profile, order.players.all())
        self.assertTrue(
            Registration.objects.filter(
                event=self.event, team=self.team, player=friend.player_profile
            ).exists()
        )

    def test_a_staff_refund_goes_back_through_the_states_account(self) -> None:
        order = self.pay_team("Pay ₹1,000")
        subscription_flows.make_staff("refunder@example.com", *subscription_flows.REFUND_PERMS)
        self.admin_sign_in("refunder@example.com", "staff-pass")
        self.refund_in_admin(order.order_id, "Refund what is left of this order", "₹1,000")
        refund = RazorpayRefund.objects.get(transaction=order)
        at_razorpay = self.state.refund.fetch(refund.razorpay_refund_id)
        self.assertEqual(order.payment_id, at_razorpay["payment_id"])
        order.refresh_from_db()
        self.assertIn(order.status, ("refunded", "completed"))  # refunded once processed

    def test_a_signed_webhook_on_the_states_url(self) -> None:
        order = RazorpayTransaction.objects.create(
            order_id=self.state.order.create({"amount": TEAM_FEE, "currency": "INR"})["id"],
            amount=TEAM_FEE,
            currency="INR",
            status="created",
            user=self.captain,
            event=self.event,
            team=self.team,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            account=self.account,
        )
        body = json.dumps(
            {
                "event": "payment.captured",
                "payload": {
                    "payment": {"entity": {"id": "pay_webhook_test", "order_id": order.order_id}}
                },
            }
        )
        good = hmac.new(
            self.account.webhook_secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        client = Client()
        # Our URL ignores it, even correctly signed for the state.
        client.post(
            "/api/transactions/razorpay/webhook",
            body,
            "application/json",
            HTTP_X_RAZORPAY_SIGNATURE=good,
        )
        order.refresh_from_db()
        self.assertEqual("created", order.status)
        client.post(
            f"/api/transactions/razorpay/webhook/{self.account.slug}",
            body,
            "application/json",
            HTTP_X_RAZORPAY_SIGNATURE=good,
        )
        order.refresh_from_db()
        self.assertEqual(COMPLETED, order.status)

    def test_the_sync_records_a_refund_made_in_the_states_dashboard(self) -> None:
        order = self.pay_team("Pay ₹1,000")
        self.state.payment.refund(order.payment_id, {"amount": 10000})
        call_command("sync_razorpay_transactions", "--no-email")
        refund = RazorpayRefund.objects.get(transaction=order)
        self.assertEqual(RazorpayRefund.Source.RAZORPAY_DASHBOARD, refund.source)
        self.assertEqual(10000, refund.amount)

    def test_the_state_sees_its_payments_and_no_one_else_does(self) -> None:
        self.pay_team("Pay ₹1,000")
        viewer = User.objects.create_user("state@example.com", "state@example.com", "pw")
        self.account.viewers.add(viewer)
        self.sign_in_as(viewer)
        self.open(f"{APP_URL}/dashboard")
        self.click('a:contains("Payments to Test State Association")')
        self.assert_text("State Testers")
        self.assert_text("₹1,000")
        # The badge is upper-cased by CSS, so match the source text.
        self.assert_element('span:contains("Test mode")')
        outsider = User.objects.create_user("out@example.com", "out@example.com", "pw")
        self.sign_in_as(outsider)
        self.open(f"{APP_URL}/payments/{self.account.slug}")
        self.assert_text("Not found")
