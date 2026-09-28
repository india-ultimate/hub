"""Every membership flow, end to end, against Razorpay's real test mode.

Each browser test pays through the real Razorpay test checkout, so money
really moves (in test mode), and every refund is a real Razorpay test refund.
Each asserts what the page shows and what the database holds. Skipped without
a Razorpay test key; never run with a live one.
"""

import hashlib
import hmac
import json
import os
import re
import uuid
from contextlib import ExitStack
from importlib import import_module
from io import StringIO

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.utils.timezone import now
from seleniumbase import BaseCase

from server.core.models import Player, User
from server.membership.emails import CONFIRMATION_SUBJECT
from server.membership.models import Membership, SponsorshipGrant
from server.season.models import Season
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.tests import test_ui
from server.tests.localserver import APP_URL, DJANGO_URL, running_test_server
from server.tests.razorpay_checkout import complete_razorpay_test_payment
from server.tests.test_ui import MAIL_DIR, make_player, queued_mail
from server.tests.utils import create_empty_directory
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

COMPLETED = RazorpayTransaction.TransactionStatusChoices.COMPLETED
REFUNDED = RazorpayTransaction.TransactionStatusChoices.REFUNDED
# A refund Razorpay accepted: it may still be settling in test mode.
TAKEN = {RazorpayRefund.Status.PROCESSED, RazorpayRefund.Status.PENDING}
NUMBER = re.compile(r"^IU-26-\d{4}$")
SEASON = "Season 2026-2027"
REFUND_PERMS = [
    "refund_razorpaytransaction",
    "view_razorpaytransaction",
    "view_razorpaytransactionplayer",
    "view_razorpayrefund",
]


def seed_catalog() -> Season:
    """Transactional tests flush what the migrations seeded; put it back."""
    import_module("server.migrations.0145_legacy_seasons").add_seasons(apps, None)
    import_module("server.migrations.0147_seed_catalog").seed(apps, None)
    import_module("server.migrations.0156_tier_features").write_copy(apps, None)
    return Season.objects.get(name=SEASON)


def make_staff(address: str, *codenames: str) -> User:
    staff = User.objects.create_user(address, address, "staff-pass", is_staff=True)
    staff.user_permissions.set(Permission.objects.filter(codename__in=codenames))
    return staff


def selected_row(name: str) -> str:
    """A person's row in the group's list: the only rows with a tier select."""
    return f'//tr[.//select][contains(., "{name}")]'


def membership_confirmations(address: str) -> list[str]:
    return [
        mail["html_content"]
        for mail in queued_mail(to=address)
        if mail["subject"] == CONFIRMATION_SUBJECT
    ]


@pytest.mark.skipif(
    not os.environ.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_"),
    reason="needs a Razorpay test-mode key",
)
@pytest.mark.django_db(transaction=True)
class TestMembershipIntegration(BaseCase):
    # The same sign-in helpers as the rest of the browser tests.
    sign_in_as = test_ui.TestIntegration.sign_in_as
    admin_sign_in = test_ui.TestIntegration.admin_sign_in

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
        create_empty_directory(MAIL_DIR)
        self.season = seed_catalog()

    def tearDown(self) -> None:
        super().tearDown()
        create_empty_directory(MAIL_DIR)

    # Helpers ####################

    def open_membership(self, player: Player) -> None:
        self.open(f"{APP_URL}/membership/{player.id}")
        self.assert_element('input[name="membership-tier"]')

    def checked_tier(self) -> str | None:
        # The radios are visually hidden, so ask the DOM, not the eye.
        return self.execute_script(
            "return document.querySelector('input[name=membership-tier]:checked')?.value"
        )

    def pay(self, button: str = 'button:contains("Pay")') -> None:
        complete_razorpay_test_payment(self, button)
        # The callback is a fetch after checkout closes; this is its result.
        self.assert_text("Payment successfully completed", timeout=60)

    def membership(self, player: Player) -> Membership:
        return Membership.objects.select_related("plan__type").get(
            player=player, season=self.season
        )

    def refund_in_admin(self, order_id: str, link: str, amount: str) -> None:
        """Click a refund button on the order's admin page, and confirm it."""
        self.open(f"{DJANGO_URL}/admin/server/razorpaytransaction/{order_id}/change/")
        self.click(f'a:contains("{link}")')
        # A confirmation page first: nothing has moved yet.
        self.assert_text(f"Refund {amount}?", "#content h1")
        self.assertFalse(RazorpayRefund.objects.filter(transaction_id=order_id).exists())
        self.type("textarea#reason", "Paid twice by mistake")
        self.click(f'input[type="submit"][value="Refund {amount}"]')
        self.assert_text("Refunded", ".messagelist", timeout=60)

    def assert_refund_taken(self, refund: RazorpayRefund, amount: int) -> None:
        self.assertEqual(refund.amount, amount)
        self.assertIn(refund.status, TAKEN)
        self.assertTrue((refund.razorpay_refund_id or "").startswith("rfnd_"))
        self.assertEqual(refund.reason, "Paid twice by mistake")

    # Flows ####################

    # Flows 1, 13, 4 and 9: buy Regular, see the number everywhere, upgrade
    # to Patron, then refund just the upgrade.
    def test_regular_then_upgrade_then_refund_the_upgrade(self) -> None:
        user = make_player("asha@example.com", first="Asha", last="Menon")
        player = Player.objects.get(user=user)

        self.sign_in_as(user)
        self.open_membership(player)
        self.assertEqual(self.checked_tier(), "regular")
        self.assert_text("Selected", 'label:contains("Regular Annual Membership")')
        self.assert_text_not_visible("Discounted Membership")
        self.assert_text("Pay ₹ 750", 'button:contains("Pay ₹")')
        self.pay()

        held = self.membership(player)
        self.assertEqual(held.tier, "regular")
        self.assertEqual(held.amount_paid, 75000)
        self.assertTrue(held.is_active)
        self.assertIsNone(held.refunded_at)
        [order] = RazorpayTransaction.objects.filter(user=user)
        self.assertEqual(order.status, COMPLETED)
        self.assertEqual(order.amount, 75000)
        player.refresh_from_db()
        number = player.membership_number
        self.assertRegex(number, NUMBER)
        self.assert_text(number, "#membership-number")
        self.assert_text("holds Regular Annual Membership", "#membership-exist")
        [mail] = membership_confirmations(user.email)
        self.assertIn(number, mail)

        # 13: the number and history on the dashboard, and on the waiver.
        self.open(f"{APP_URL}/dashboard")  # the player section starts open
        self.assert_text(number, "#accordion-body-player")
        self.assert_text("Membership history", "#accordion-body-player")
        self.assert_text(f"{SEASON} — Regular Annual Membership", "#accordion-body-player")
        self.open(f"{APP_URL}/waiver/{player.id}")
        self.assert_text(f"Membership number: {number}")
        self.js_click("input#waiver")
        self.js_click("input#legal")
        self.click('button:contains("I Agree")')
        self.assert_text(f"Membership number: {number}.", 'div[role="alert"]')
        self.assertTrue(self.membership(player).waiver_valid)

        # 4: Patron costs only the difference, and is the only thing on sale.
        self.open_membership(player)
        self.assert_text("Your current tier", 'label:contains("Regular Annual Membership")')
        self.assert_text("Upgrade for ₹750", 'label:contains("Patron member")')
        self.assertEqual(self.checked_tier(), "patron")
        upgrade = 'button:contains("Upgrade from Regular Annual Membership")'
        self.assert_text("pay ₹ 750", upgrade)
        self.pay(upgrade)

        upgraded = self.membership(player)
        self.assertEqual(upgraded.pk, held.pk)
        self.assertEqual(upgraded.tier, "patron")
        self.assertEqual(upgraded.amount_paid, 150000)
        self.assertTrue(upgraded.is_active)
        self.assertEqual(Membership.objects.filter(player=player).count(), 1)
        player.refresh_from_db()
        self.assertEqual(player.membership_number, number)
        self.assert_text("holds Patron member", "#membership-exist")
        second = RazorpayTransaction.objects.exclude(pk=order.pk).get(user=user)
        self.assertEqual(second.amount, 75000)
        self.assertEqual(second.status, COMPLETED)
        self.assertEqual(len(membership_confirmations(user.email)), 2)

        # 9: refunding the upgrade puts them back on Regular, still a member.
        make_staff("refunds@example.com", *REFUND_PERMS)
        self.admin_sign_in("refunds@example.com", "staff-pass")
        self.refund_in_admin(second.pk, "Refund ₹750", "₹750")
        [refund] = RazorpayRefund.objects.all()
        self.assert_refund_taken(refund, 75000)
        self.assertEqual(refund.transaction_id, second.pk)
        self.assertTrue(RazorpayRefund.objects.filter(line__transaction=second).exists())
        back = self.membership(player)
        self.assertEqual(back.tier, "regular")
        self.assertEqual(back.amount_paid, 75000)
        self.assertTrue(back.is_active)
        self.assertIsNone(back.refunded_at)
        second.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(second.status, REFUNDED)
        self.assertEqual(order.status, COMPLETED)

        # And the upgrade is on offer again.
        self.sign_in_as(user)
        self.open_membership(player)
        self.assert_element('button:contains("Upgrade from Regular Annual Membership")')

    # Flows 2, 7 and 11: buy Patron, staff refund it, and the nightly sync
    # against Razorpay's real records changes nothing.
    def test_patron_refunded_by_staff_then_synced(self) -> None:
        user = make_player("vikram@example.com", first="Vikram", last="Singh")
        player = Player.objects.get(user=user)

        self.sign_in_as(user)
        self.open_membership(player)
        self.click('label:contains("Patron member")')
        self.assertEqual(self.checked_tier(), "patron")
        self.assert_text("Selected", 'label:contains("Patron member")')
        self.assert_text("Pay ₹ 1,500", 'button:contains("Pay ₹")')
        self.pay()

        held = self.membership(player)
        self.assertEqual(held.tier, "patron")
        self.assertEqual(held.amount_paid, 150000)
        self.assertTrue(held.is_active)
        self.assert_text("holds Patron member", "#membership-exist")
        [order] = RazorpayTransaction.objects.filter(user=user)
        self.assertEqual(order.status, COMPLETED)

        # 7: one person's line, refunded by staff who hold the permission.
        make_staff("refunds@example.com", *REFUND_PERMS)
        self.admin_sign_in("refunds@example.com", "staff-pass")
        self.refund_in_admin(order.pk, "Refund ₹1500", "₹1,500")
        [refund] = RazorpayRefund.objects.all()
        self.assert_refund_taken(refund, 150000)
        held.refresh_from_db()
        self.assertIsNotNone(held.refunded_at)
        self.assertFalse(held.is_active)
        self.assertFalse(Membership.objects.live().filter(pk=held.pk).exists())
        order.refresh_from_db()
        self.assertEqual(order.status, REFUNDED)

        # The player can buy the season again.
        self.sign_in_as(user)
        self.open_membership(player)
        self.assert_element_absent("#membership-exist")
        self.assertEqual(self.checked_tier(), "regular")
        self.assert_text("Pay ₹ 750", 'button:contains("Pay ₹")')

        # 11: the sync reads Razorpay's real payments and refunds since today.
        mails = len(queued_mail())
        for _ in range(2):
            call_command(
                "sync_razorpay_transactions",
                "--since",
                now().date().isoformat(),
                "--no-email",
                stdout=StringIO(),
            )
        self.assertEqual(len(queued_mail()), mails)
        [synced] = RazorpayRefund.objects.all()
        self.assertEqual(synced.razorpay_refund_id, refund.razorpay_refund_id)
        self.assertIn(synced.status, TAKEN)
        self.assertEqual(synced.source, RazorpayRefund.Source.HUB)
        order.refresh_from_db()
        self.assertEqual(order.status, REFUNDED)
        held.refresh_from_db()
        self.assertIsNotNone(held.refunded_at)
        self.assertFalse(held.is_active)
        self.assertEqual(Membership.objects.filter(player=player).count(), 1)
        self.assertEqual(RazorpayTransaction.objects.count(), 1)
        self.assertFalse(RazorpayTransactionPlayer.objects.filter(needs_review=True).exists())

    # Flows 3 and 10: buy Community, and nobody without the permission can
    # refund it.
    def test_community_and_who_may_not_refund(self) -> None:
        user = make_player("neha@example.com", first="Neha", last="Kapoor")
        player = Player.objects.get(user=user)

        self.sign_in_as(user)
        self.open_membership(player)
        self.click('label:contains("Community Membership")')
        self.assertEqual(self.checked_tier(), "community")
        self.assert_text("Pay ₹ 250", 'button:contains("Pay ₹")')
        self.pay()

        held = self.membership(player)
        self.assertEqual(held.tier, "community")
        self.assertEqual(held.amount_paid, 25000)
        self.assertTrue(held.is_active)
        self.assert_text("holds Community Membership", "#membership-exist")
        [order] = RazorpayTransaction.objects.filter(user=user)
        line = RazorpayTransactionPlayer.objects.get(transaction=order)
        refund_pages = [
            f"/admin/refund-line/{line.pk}/",
            f"/admin/refund-order/{order.pk}/",
            f"/admin/refund-membership/{held.pk}/",
        ]

        # Staff who may see payments but not refund them: no buttons, and
        # every refund page refuses, on GET and on POST.
        make_staff("viewer@example.com", *[p for p in REFUND_PERMS if p.startswith("view_")])
        self.admin_sign_in("viewer@example.com", "staff-pass")
        self.open(f"{DJANGO_URL}/admin/server/razorpaytransaction/{order.pk}/change/")
        self.assert_text(order.pk)
        self.assert_element_absent('a:contains("Refund ₹")')
        self.assert_element_absent('a:contains("Refund what is left")')
        viewer = Client()
        viewer.force_login(User.objects.get(username="viewer@example.com"))
        for page in refund_pages:
            self.open(f"{DJANGO_URL}{page}")
            self.assert_text("403 Forbidden")
            self.assert_element_absent("textarea#reason")
            response = viewer.post(page, {"reason": "not allowed"})
            self.assertEqual(response.status_code, 403)

        # A plain signed-in player is sent to the admin's sign-in instead.
        self.sign_in_as(user)
        member = Client()
        member.force_login(user)
        for page in refund_pages:
            self.open(f"{DJANGO_URL}{page}")
            self.assert_element("input#id_username")
            self.assert_element_absent("textarea#reason")
            response = member.post(page, {"reason": "not allowed"})
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login/", response["Location"])

        self.assertFalse(RazorpayRefund.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, COMPLETED)
        held.refresh_from_db()
        self.assertTrue(held.is_active)
        self.assertIsNone(held.refunded_at)

    # Flow 5: ask for a discount, staff approve it in the admin, and pay the
    # discounted price.
    def test_sponsorship_from_request_to_payment(self) -> None:
        user = make_player("ravi@example.com", first="Ravi", last="Kumar")
        player = Player.objects.get(user=user)

        self.sign_in_as(user)
        self.open_membership(player)
        self.click('button:contains("Request a discounted membership")')
        self.assert_text(f"For {SEASON}")
        self.type("textarea", "I am a student and can't pay the full fee this year.")
        self.click('button:contains("+ Add Myself")')
        self.click('button:contains("Submit Request")')
        self.assert_text("Service request submitted successfully!")
        [request] = ServiceRequest.objects.all()
        self.assertEqual(request.type, ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP)
        self.assertEqual(request.season_id, self.season.id)
        self.assertEqual(request.user_id, user.id)
        self.assertEqual(list(request.service_players.all()), [player])
        self.assertEqual(request.status, ServiceRequestStatus.PENDING)
        self.assertFalse(SponsorshipGrant.objects.exists())

        # Staff approve it with the admin action.
        staff = User.objects.create_superuser("ops@example.com", "ops@example.com", "staff-pass")
        self.admin_sign_in("ops@example.com", "staff-pass")
        self.open(f"{DJANGO_URL}/admin/server/servicerequest/")
        self.click(f"input[name=_selected_action][value='{request.pk}']")
        self.select_option_by_value("select[name=action]", "approve_sponsorship")
        self.click("button[name=index]")
        self.assert_text(f"Request {request.pk}: 1 player(s) sponsored for {SEASON}")
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequestStatus.APPROVED)
        grant = SponsorshipGrant.objects.get(player=player, season=self.season)
        self.assertEqual(grant.granted_by_id, staff.id)
        self.assertEqual(grant.request_id, request.pk)

        # Discounted replaces Regular, approved and selected.
        self.sign_in_as(user)
        self.open_membership(player)
        self.assert_text("Approved for you", 'label:contains("Discounted Membership")')
        self.assert_text_not_visible("Regular Annual Membership")
        self.assertEqual(self.checked_tier(), "discounted")
        self.assert_text("Pay ₹ 300", 'button:contains("Pay ₹")')
        self.pay()

        held = self.membership(player)
        self.assertEqual(held.tier, "discounted")
        self.assertEqual(held.amount_paid, 30000)
        self.assertTrue(held.is_active)
        self.assert_text("holds Discounted Membership", "#membership-exist")

    # Flows 6 and 8: one person pays for two, each on their own tier, then
    # staff refund the whole order.
    def test_group_payment_then_refund_the_whole_order(self) -> None:
        payer = make_player("captain@example.com", first="Arjun", last="Captain")
        kiran = Player.objects.get(user=make_player("kiran@example.com", first="Kiran", last="Rao"))
        meera = Player.objects.get(
            user=make_player("meera@example.com", first="Meera", last="Iyer")
        )
        SponsorshipGrant.objects.create(player=kiran, season=self.season)

        self.sign_in_as(payer)
        self.open_membership(Player.objects.get(user=payer))
        self.click("button#group-tab")
        for name in ("Kiran Rao", "Meera Iyer"):
            self.type("input#player-search", f"{name}\n")
            self.click(f'tr:contains("{name}") button:contains("Add")')
            self.assert_element(selected_row(name))

        kiran_row, meera_row = selected_row("Kiran Rao"), selected_row("Meera Iyer")

        def shown(row: str) -> str:
            # What the browser displays, which is what the Solid bug got wrong,
            # and not merely the select's value.
            return self.execute_script(
                "const s = arguments[0]; return s.options[s.selectedIndex].value;",
                self.find_element(f"{row}//select"),
            )

        self.assertEqual(shown(kiran_row), "discounted")
        self.assertEqual(shown(meera_row), "regular")
        self.assert_text("₹ 300", f"{kiran_row}/td[2]")
        self.assert_text("₹ 750", f"{meera_row}/td[2]")
        # The total is printed unformatted, unlike the fees and the button.
        self.assert_text("Total Amount: ₹1050")

        self.select_option_by_value(f"{meera_row}//select", "community")
        self.assertEqual(shown(meera_row), "community")
        self.assertEqual(shown(kiran_row), "discounted")
        self.assert_text("₹ 250", f"{meera_row}/td[2]")
        self.assert_text("₹ 300", f"{kiran_row}/td[2]")
        self.assert_text("Total Amount: ₹550")
        self.assert_text("Pay ₹ 550", 'button:contains("Pay ₹")')
        self.pay('button:contains("Pay ₹")')

        [order] = RazorpayTransaction.objects.filter(user=payer)
        self.assertEqual(order.amount, 55000)
        self.assertEqual(order.status, COMPLETED)
        self.assertFalse(Membership.objects.filter(player__user=payer).exists())
        for player, slug, amount in ((kiran, "discounted", 30000), (meera, "community", 25000)):
            held = self.membership(player)
            self.assertEqual(held.tier, slug)
            self.assertEqual(held.amount_paid, amount)
            self.assertTrue(held.is_active)
            line = RazorpayTransactionPlayer.objects.get(transaction=order, player=player)
            self.assertEqual((line.amount, line.membership_id), (amount, held.pk))
            player.refresh_from_db()
            self.assertRegex(player.membership_number, NUMBER)
        self.assertNotEqual(kiran.membership_number, meera.membership_number)

        # 8: the whole order back, one refund per person.
        make_staff("refunds@example.com", *REFUND_PERMS)
        self.admin_sign_in("refunds@example.com", "staff-pass")
        self.refund_in_admin(order.pk, "Refund what is left of this order", "₹550")
        self.assertEqual(RazorpayRefund.objects.filter(transaction=order).count(), 2)
        self.assert_refund_taken(RazorpayRefund.objects.get(line__player=kiran), 30000)
        self.assert_refund_taken(RazorpayRefund.objects.get(line__player=meera), 25000)
        for player in (kiran, meera):
            held = self.membership(player)
            self.assertIsNotNone(held.refunded_at)
            self.assertFalse(held.is_active)
        order.refresh_from_db()
        self.assertEqual(order.status, REFUNDED)

    # Flow 12: Razorpay's signed webhook, for a real order. No browser needed.
    def test_signed_webhook(self) -> None:
        user = make_player("hook@example.com", first="Hari", last="Webb")
        player = Player.objects.get(user=user)
        other = Player.objects.get(user=make_player("idle@example.com", first="Ida", last="Le"))
        client = Client()
        client.force_login(user)

        def order_for(buyer: Player, tier: str) -> str:
            response = client.post(
                "/api/transactions/razorpay",
                {
                    "season_id": self.season.id,
                    "items": [{"player_id": buyer.id, "plan_type": tier}],
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)
            return response.json()["order_id"]

        def hook(event: str, order_id: str, signature: str | None = None) -> str:
            body = json.dumps(
                {
                    "entity": "event",
                    "event": event,
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": f"pay_{uuid.uuid4().hex[:14]}",
                                "order_id": order_id,
                                "status": "captured",
                            }
                        }
                    },
                }
            )
            # Exactly as Razorpay signs it: HMAC-SHA256 of the raw body.
            expected = hmac.new(
                settings.RAZORPAY_WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256
            ).hexdigest()
            response = client.post(
                "/api/transactions/razorpay/webhook",
                body,
                content_type="application/json",
                HTTP_X_RAZORPAY_SIGNATURE=signature or expected,
            )
            self.assertEqual(response.status_code, 200)
            return response.json()["message"]

        order_id = order_for(player, "regular")
        self.assertTrue(order_id.startswith("order_"))
        order = RazorpayTransaction.objects.get(pk=order_id)
        self.assertNotIn(order.status, RazorpayTransaction.SETTLED)

        self.assertEqual(
            hook("payment.captured", order_id, "0" * 64), "Signature could not be verified"
        )
        self.assertFalse(Membership.objects.exists())

        self.assertEqual(hook("payment.captured", order_id), "Webhook processed")
        order.refresh_from_db()
        self.assertEqual(order.status, COMPLETED)
        held = self.membership(player)
        self.assertEqual((held.tier, held.amount_paid, held.is_active), ("regular", 75000, True))
        self.assertEqual(len(membership_confirmations(user.email)), 1)
        payment_id = order.payment_id

        # Razorpay retries: a replay is recognised and changes nothing.
        self.assertEqual(hook("payment.captured", order_id), "Already processed")
        self.assertEqual(hook("order.paid", order_id), "Already processed")
        order.refresh_from_db()
        self.assertEqual(order.payment_id, payment_id)
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(len(membership_confirmations(user.email)), 1)

        # An event it does not act on leaves an unpaid order unpaid.
        idle = order_for(other, "community")
        self.assertEqual(hook("payment.authorized", idle), "Ignored webhook")
        self.assertNotIn(
            RazorpayTransaction.objects.get(pk=idle).status, RazorpayTransaction.SETTLED
        )
        self.assertFalse(Membership.objects.filter(player=other).exists())

        # order.paid is the other event it accepts.
        self.assertEqual(hook("order.paid", idle), "Webhook processed")
        self.assertEqual(self.membership(other).tier, "community")
