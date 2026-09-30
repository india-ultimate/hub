import datetime
from typing import Any
from unittest import mock

from django.contrib.admin.sites import site
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from server.admin import PlayerAdmin
from server.core.models import Player, User
from server.season.models import Season
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.subscription import purchase
from server.subscription.models import SponsorshipGrant, Subscription, SubscriptionPlan
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

from .test_subscription_model import make_player

ACCEPTED = {"id": "rfnd_admin", "status": "processed"}

# Admin templates pull hashed static files, which the test tree has no
# manifest for.
ADMIN_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def staff_user(email: str, *, refunds: bool = False, everything: bool = False) -> User:
    """A staff account. `everything` is a superuser; `refunds` only adds the one."""
    user = User.objects.create(username=email, email=email, is_staff=True, is_superuser=everything)
    user.set_password("pw")
    user.save()
    if refunds:
        user.user_permissions.add(Permission.objects.get(codename="refund_razorpaytransaction"))
    return user


class RefundAdminTestCase(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("n@example.com")
        self.plan = SubscriptionPlan.objects.get(season=self.season, type__slug="regular")
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_admin",
            payment_id="pay_admin",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        self.line = RazorpayTransactionPlayer.objects.create(
            transaction=self.transaction, player=self.player, plan=self.plan, amount=75000
        )
        purchase.fulfil(self.transaction)
        self.subscription = Subscription.objects.get(player=self.player, season=self.season)


@override_settings(STORAGES=ADMIN_STORAGES)
class TestRefundPermission(RefundAdminTestCase):
    def test_staff_without_the_permission_cannot_refund(self) -> None:
        self.client.force_login(staff_user("plain@example.com"))
        response = self.client.post(
            reverse("admin:refund_line", args=[self.line.pk]), data={"reason": "test"}
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(self.line.refunds.exists())

    def test_staff_without_the_permission_cannot_see_the_page(self) -> None:
        self.client.force_login(staff_user("plain2@example.com"))
        response = self.client.get(reverse("admin:refund_line", args=[self.line.pk]))
        self.assertIn(response.status_code, (302, 403))

    def test_a_stranger_cannot_refund(self) -> None:
        response = self.client.post(
            reverse("admin:refund_line", args=[self.line.pk]), data={"reason": "test"}
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(self.line.refunds.exists())

    def test_the_permission_is_needed_on_every_refund_page(self) -> None:
        self.client.force_login(staff_user("plain3@example.com"))
        for url in (
            reverse("admin:refund_subscription", args=[self.subscription.pk]),
            reverse("admin:refund_order", args=[self.transaction.pk]),
        ):
            response = self.client.post(url, data={"reason": "test"})
            self.assertIn(response.status_code, (302, 403), url)
        self.assertFalse(RazorpayRefund.objects.exists())

    def test_staff_with_the_permission_see_the_confirmation(self) -> None:
        self.client.force_login(staff_user("allowed@example.com", refunds=True))
        with mock.patch("server.transaction.client.razorpay.CLIENT.payment.refund") as gateway:
            response = self.client.get(reverse("admin:refund_line", args=[self.line.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "750")
        # A GET must never move money.
        gateway.assert_not_called()
        self.assertFalse(RazorpayRefund.objects.exists())


@override_settings(STORAGES=ADMIN_STORAGES)
class TestRefundViews(RefundAdminTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff = staff_user("refunder@example.com", refunds=True, everything=True)
        self.client.force_login(self.staff)

    def test_confirming_refunds_the_line(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            response = self.client.post(
                reverse("admin:refund_line", args=[self.line.pk]),
                data={"reason": "left the sport"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.refunded_at)
        refund = RazorpayRefund.objects.get()
        self.assertEqual(refund.amount, 75000)
        self.assertEqual(refund.created_by, self.staff)

    def test_a_second_refund_of_the_same_line_is_refused(self) -> None:
        url = reverse("admin:refund_line", args=[self.line.pk])
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            self.client.post(url, data={"reason": "first"})
            response = self.client.post(url, data={"reason": "second"}, follow=True)
        self.assertEqual(RazorpayRefund.objects.count(), 1)
        self.assertContains(response, "already been refunded")

    def test_refunding_a_subscription_reports_what_moved(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            response = self.client.post(
                reverse("admin:refund_subscription", args=[self.subscription.pk]),
                data={"reason": "quit"},
                follow=True,
            )
        self.assertContains(response, "Refunded ₹750")
        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.refunded_at)

    def test_a_historical_order_warns_the_subscription_stays(self) -> None:
        # Every payment made before tiers has lines with no tier and no amount.
        player = make_player("old@example.com")
        subscription = Subscription.objects.create(
            player=player,
            season=self.season,
            plan=self.plan,
            amount_paid=75000,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            is_active=True,
        )
        old = RazorpayTransaction.objects.create(
            order_id="order_old",
            payment_id="pay_old",
            amount=75000,
            currency="INR",
            user=player.user,
            season=self.season,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            type=RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
        )
        line = RazorpayTransactionPlayer.objects.create(transaction=old, player=player)

        for url in (
            reverse("admin:refund_order", args=[old.pk]),
            reverse("admin:refund_line", args=[line.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, "Deactivate it by hand", msg_prefix=url)
            self.assertContains(
                response, f"{self.season.name} subscription (#{subscription.pk})", msg_prefix=url
            )
            self.assertNotContains(response, "stops counting", msg_prefix=url)
            self.assertNotContains(response, "not a subscription", msg_prefix=url)

    def test_refunding_a_whole_order_goes_back_to_it(self) -> None:
        url = reverse("admin:refund_order", args=[self.transaction.pk])
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            response = self.client.post(url, data={"reason": "event cancelled"})
        self.assertRedirects(
            response,
            reverse("admin:server_razorpaytransaction_change", args=[self.transaction.pk]),
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(response["Location"]), "Refunded ₹750.")
        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.refunded_at)

    def test_refunding_a_historical_order_leaves_the_subscription_alone(self) -> None:
        """Paid before tiers: the money goes back whole, and the page warns
        that nothing else changes, even when the subscription can't be found."""
        player = make_player("old@example.com")
        old = RazorpayTransaction.objects.create(
            order_id="order_old",
            payment_id="pay_old",
            amount=70000,
            currency="INR",
            user=player.user,
            season=self.season,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(transaction=old, player=player)
        url = reverse("admin:refund_order", args=[old.pk])

        self.assertContains(self.client.get(url), "the subscription it paid for stays")

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ) as gateway:
            self.client.post(url, data={"reason": "duplicate payment"})
        gateway.assert_called_once_with("pay_old", mock.ANY)
        self.assertEqual(RazorpayRefund.objects.get(transaction=old).amount, 70000)

    def test_a_registration_order_warns_it_is_not_a_subscription(self) -> None:
        team_order = RazorpayTransaction.objects.create(
            order_id="order_team",
            payment_id="pay_team",
            amount=500000,
            currency="INR",
            user=self.player.user,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        response = self.client.get(reverse("admin:refund_order", args=[team_order.pk]))
        self.assertContains(response, "not a subscription")

    def test_razorpay_refusing_a_whole_order_refund_is_shown_and_recorded(self) -> None:
        team_order = RazorpayTransaction.objects.create(
            order_id="order_team",
            payment_id="pay_team",
            amount=500000,
            currency="INR",
            user=self.player.user,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            side_effect=Exception("insufficient balance"),
        ):
            response = self.client.post(
                reverse("admin:refund_order", args=[team_order.pk]),
                data={"reason": "withdrew"},
                follow=True,
            )
        self.assertContains(response, "Razorpay refused the refund: insufficient balance")
        # The failed attempt is kept, for the nightly sync and for staff.
        refund = RazorpayRefund.objects.get(transaction=team_order)
        self.assertEqual(refund.status, RazorpayRefund.Status.FAILED)
        self.assertEqual(refund.error, "insufficient balance")
        team_order.refresh_from_db()
        self.assertEqual(team_order.status, RazorpayTransaction.TransactionStatusChoices.COMPLETED)

    def test_refunding_an_order_whose_lines_are_refunded_is_refused(self) -> None:
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", return_value=ACCEPTED
        ):
            self.client.post(
                reverse("admin:refund_line", args=[self.line.pk]), data={"reason": "first"}
            )
            response = self.client.post(
                reverse("admin:refund_order", args=[self.transaction.pk]),
                data={"reason": "again"},
                follow=True,
            )
        self.assertContains(response, "This order has already been refunded.")
        self.assertEqual(RazorpayRefund.objects.count(), 1)

    def test_an_order_refund_without_a_reason_is_refused(self) -> None:
        team_order = RazorpayTransaction.objects.create(
            order_id="order_team",
            payment_id="pay_team",
            amount=500000,
            currency="INR",
            user=self.player.user,
            type=RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        with mock.patch("server.transaction.client.razorpay.CLIENT.payment.refund") as gateway:
            response = self.client.post(
                reverse("admin:refund_order", args=[team_order.pk]),
                data={"reason": "   "},
                follow=True,
            )
        self.assertContains(response, "A refund needs a reason.")
        gateway.assert_not_called()
        self.assertFalse(RazorpayRefund.objects.exists())

    def test_refunding_a_subscription_says_what_moved_before_it_stopped(self) -> None:
        patron = SubscriptionPlan.objects.get(season=self.season, type__slug="patron")
        upgrade = RazorpayTransaction.objects.create(
            order_id="order_upgrade",
            payment_id="pay_upgrade",
            amount=75000,
            currency="INR",
            user=self.player.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=upgrade, player=self.player, plan=patron, amount=75000
        )
        purchase.fulfil(upgrade)

        # The upgrade goes back first, then the gateway fails on the original.
        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund",
            side_effect=[ACCEPTED, RuntimeError("gateway is down")],
        ):
            response = self.client.post(
                reverse("admin:refund_subscription", args=[self.subscription.pk]),
                data={"reason": "quit"},
                follow=True,
            )

        self.assertContains(response, "Stopped after refunding ₹750 on 1 payment(s)")
        self.assertContains(response, "gateway is down")
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.is_active)
        self.assertEqual(self.subscription.plan, self.plan)


@override_settings(STORAGES=ADMIN_STORAGES)
class TestPartialRefund(TestCase):
    """A later line can be refused after earlier ones have already paid out."""

    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.plan = SubscriptionPlan.objects.get(season=self.season, type__slug="regular")
        self.buyer = make_player("buyer@example.com")
        self.friend = make_player("friend@example.com")
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_pair",
            payment_id="pay_pair",
            amount=150000,
            currency="INR",
            user=self.buyer.user,
            season=self.season,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        for player in (self.buyer, self.friend):
            RazorpayTransactionPlayer.objects.create(
                transaction=self.transaction, player=player, plan=self.plan, amount=75000
            )
        purchase.fulfil(self.transaction)
        self.client.force_login(staff_user("partial@example.com", refunds=True, everything=True))

    def test_the_page_says_what_already_moved(self) -> None:
        def gateway(payment_id: str, data: dict[str, Any]) -> dict[str, str]:
            if gateway.calls:  # type: ignore[attr-defined]
                raise RuntimeError("gateway is down")
            gateway.calls = 1  # type: ignore[attr-defined]
            return ACCEPTED

        gateway.calls = 0  # type: ignore[attr-defined]

        with mock.patch(
            "server.transaction.client.razorpay.CLIENT.payment.refund", side_effect=gateway
        ):
            response = self.client.post(
                reverse("admin:refund_order", args=[self.transaction.pk]),
                data={"reason": "event cancelled"},
                follow=True,
            )

        self.assertContains(response, "Stopped after refunding ₹750")
        self.assertContains(response, "gateway is down")
        self.assertEqual(RazorpayRefund.objects.filter(status="processed").count(), 1)
        self.assertEqual(RazorpayRefund.objects.filter(status="failed").count(), 1)


@override_settings(STORAGES=ADMIN_STORAGES)
class TestAdminScreens(RefundAdminTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff = staff_user("super@example.com")
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)

    def test_flagged_payments_are_one_filter_away(self) -> None:
        self.line.needs_review = True
        self.line.save(update_fields=["needs_review"])
        clean = RazorpayTransaction.objects.create(
            order_id="order_clean",
            payment_id="pay_clean",
            amount=1000,
            currency="INR",
            user=self.player.user,
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
        )
        url = reverse("admin:server_razorpaytransaction_changelist")
        flagged = self.client.get(url, {"needs_review": "yes"})
        self.assertContains(flagged, self.transaction.pk)
        self.assertNotContains(flagged, clean.pk)
        unflagged = self.client.get(url, {"needs_review": "no"})
        self.assertContains(unflagged, clean.pk)
        self.assertNotContains(unflagged, self.transaction.pk)

    def test_refund_completely_takes_one_subscription_at_a_time(self) -> None:
        other = make_player("other@example.com")
        second = Subscription.objects.create(
            player=other,
            season=self.season,
            plan=self.plan,
            is_active=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        url = reverse("admin:server_subscription_changelist")
        with mock.patch("server.transaction.client.razorpay.CLIENT.payment.refund") as gateway:
            response = self.client.post(
                url,
                data={
                    "action": "refund_completely",
                    "_selected_action": [str(self.subscription.pk), str(second.pk)],
                },
                follow=True,
            )
        self.assertContains(response, "Refund one subscription at a time")
        gateway.assert_not_called()

        # One row goes to the confirmation page, and still moves no money.
        response = self.client.post(
            url, data={"action": "refund_completely", "_selected_action": [str(second.pk)]}
        )
        self.assertRedirects(
            response,
            reverse("admin:refund_subscription", args=[second.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(RazorpayRefund.objects.exists())

    def test_the_player_form_cannot_set_sponsored_or_a_number(self) -> None:
        # The change form, not just the list: a sponsored checkbox here would
        # grant nothing, and the number is for life.
        request = RequestFactory().get("/")
        request.user = self.staff
        form = PlayerAdmin(Player, site).get_form(request, self.player)
        self.assertNotIn("sponsored", form.base_fields)
        self.assertNotIn("iu_id", form.base_fields)

    def test_the_subscription_screen_does_not_lie_about_sponsorship(self) -> None:
        response = self.client.get(reverse("admin:server_subscription_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Sponsored")

    def test_the_refund_button_is_hidden_without_the_permission(self) -> None:
        url = reverse("admin:server_razorpaytransaction_change", args=[self.transaction.pk])
        line_link = reverse("admin:refund_line", args=[self.line.pk])
        order_link = reverse("admin:refund_order", args=[self.transaction.pk])
        self.assertContains(self.client.get(url), line_link)
        self.assertContains(self.client.get(url), order_link)

        viewer = staff_user("viewer@example.com")
        viewer.user_permissions.add(
            Permission.objects.get(codename="view_razorpaytransaction"),
            Permission.objects.get(codename="view_razorpaytransactionplayer"),
        )
        self.client.force_login(viewer)
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, line_link)
        self.assertNotContains(page, order_link)

    def test_a_new_season_copies_the_previous_plans(self) -> None:
        response = self.client.post(
            reverse("admin:server_season_add"),
            data={
                "name": "Season 2027-2028",
                "start_date": "2027-08-01",
                "end_date": "2028-07-31",
                "annual_subscription_amount": 0,
                "sponsored_annual_subscription_amount": 0,
                "supporter_annual_subscription_amount": 0,
                "plans-TOTAL_FORMS": "0",
                "plans-INITIAL_FORMS": "0",
                "plans-MIN_NUM_FORMS": "0",
                "plans-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        new = Season.objects.get(name="Season 2027-2028")
        self.assertEqual(
            set(SubscriptionPlan.objects.filter(season=new).values_list("type__slug", flat=True)),
            set(
                SubscriptionPlan.objects.filter(season=self.season).values_list(
                    "type__slug", flat=True
                )
            ),
        )


@override_settings(STORAGES=ADMIN_STORAGES)
class TestApproveSponsorship(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("asker@example.com")
        self.staff = staff_user("approver@example.com")
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)

    def approve(self, item: ServiceRequest) -> None:
        self.client.post(
            reverse("admin:server_servicerequest_changelist"),
            data={"action": "approve_sponsorship", "_selected_action": [str(item.pk)]},
        )

    def test_approving_grants_the_season_and_records_who(self) -> None:
        item = ServiceRequest.objects.create(
            user=self.player.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="please",
            season=self.season,
        )
        item.service_players.add(self.player)

        self.approve(item)

        item.refresh_from_db()
        self.assertEqual(item.status, ServiceRequestStatus.APPROVED)
        grant = SponsorshipGrant.objects.get(player=self.player, season=self.season)
        self.assertEqual(grant.granted_by, self.staff)
        self.assertEqual(grant.request, item)

    def test_a_request_created_already_approved_still_grants(self) -> None:
        # The post_save signal cannot help here: the M2M players are attached
        # after the request is saved, so nothing was granted at that point.
        item = ServiceRequest.objects.create(
            user=self.player.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="please",
            season=self.season,
            status=ServiceRequestStatus.APPROVED,
        )
        item.service_players.add(self.player)
        self.assertFalse(SponsorshipGrant.objects.filter(player=self.player).exists())

        self.approve(item)

        self.assertTrue(
            SponsorshipGrant.objects.filter(player=self.player, season=self.season).exists()
        )

    def test_a_request_with_no_season_to_grant_is_left_pending(self) -> None:
        item = ServiceRequest.objects.create(
            user=self.player.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="please",
        )
        item.service_players.add(self.player)

        # No season on the request, and today falls in none.
        with mock.patch("server.season.models.today", return_value=datetime.date(2019, 1, 1)):
            response = self.client.post(
                reverse("admin:server_servicerequest_changelist"),
                data={"action": "approve_sponsorship", "_selected_action": [str(item.pk)]},
                follow=True,
            )

        self.assertContains(response, f"Request {item.pk}: no season to grant")
        item.refresh_from_db()
        self.assertNotEqual(item.status, ServiceRequestStatus.APPROVED)
        self.assertFalse(SponsorshipGrant.objects.exists())


@override_settings(STORAGES=ADMIN_STORAGES)
class TestOrderPageLoads(RefundAdminTestCase):
    def queries_to_open_the_order(self) -> int:
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                reverse("admin:server_razorpaytransaction_change", args=[self.transaction.pk])
            )
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def test_the_order_page_does_not_grow_with_the_hub(self) -> None:
        self.client.force_login(staff_user("boss@example.com", everything=True))
        before = self.queries_to_open_the_order()

        for n in range(20):
            other = make_player(f"other{n}@example.com")
            Subscription.objects.create(
                player=other,
                season=self.season,
                plan=self.plan,
                start_date=self.season.start_date,
                end_date=self.season.end_date,
            )

        # Dropdowns of every player and subscription cost queries per option,
        # and timed out in production once the Hub had thousands of each.
        self.assertEqual(self.queries_to_open_the_order(), before)
