from typing import Any

from django.conf import settings

from server.core.models import Player, Team, User
from server.forms.models import Form, FormResponse
from server.mcp.pay import pay_link
from server.season.models import Season
from server.subscription.models import SubscriptionPlan
from server.tests.base import ApiBaseTestCase, create_player, make_account
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer


class TestPayOrder(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def order(self, **fields: object) -> RazorpayTransaction:
        values: dict[str, object] = {
            "order_id": "order_1",
            "amount": 50000,
            "currency": "INR",
            "status": "created",
            "user": self.user,
            "type": "player-reg",
            "event": self.event,
            **fields,
        }
        return RazorpayTransaction.objects.create(**values)

    def test_owner_gets_what_checkout_needs(self) -> None:
        self.order()
        response = self.client.get("/api/transactions/razorpay/orders/order_1")
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(
            ("order_1", 50000, "INR"), (body["order_id"], body["amount"], body["currency"])
        )
        self.assertEqual(
            "Player registration payment by John Williamson for , event: NCS Sectionals 2023",
            body["description"],
        )
        self.assertEqual("username@foo.com", body["prefill"]["email"])
        self.assertEqual(settings.RAZORPAY_KEY_ID, body["key"])
        self.assertEqual(settings.APP_NAME, body["name"])

    def test_a_team_account_order_uses_its_own_key_and_name(self) -> None:
        account = make_account()
        team = Team.objects.create(name="Bangalore Hustle", slug="hustle")
        self.order(type="team-reg", account=account, team=team)
        body = self.client.get("/api/transactions/razorpay/orders/order_1").json()
        self.assertEqual(account.key_id, body["key"])
        self.assertEqual("Karnataka Ultimate", body["name"])
        self.assertEqual(
            "Team registration payment by John Williamson for Bangalore Hustle, event: NCS Sectionals 2023",
            body["description"],
        )

    def test_someone_else_cannot_see_it(self) -> None:
        self.order()
        other = User.objects.create(username="o@foo.com", email="o@foo.com")
        self.client.force_login(other)
        self.assertEqual(
            404, self.client.get("/api/transactions/razorpay/orders/order_1").status_code
        )

    def test_a_paid_order_is_refused(self) -> None:
        self.order(status="completed")
        response = self.client.get("/api/transactions/razorpay/orders/order_1")
        self.assertEqual(409, response.status_code)
        self.assertEqual("This order is already paid", response.json()["message"])

    def test_unknown_order_is_404(self) -> None:
        self.assertEqual(404, self.client.get("/api/transactions/razorpay/orders/nope").status_code)

    def test_a_refunded_order_is_refused_with_the_reason(self) -> None:
        self.order(status="refunded")
        response = self.client.get("/api/transactions/razorpay/orders/order_1")
        self.assertEqual(409, response.status_code)
        self.assertEqual("This order is refunded", response.json()["message"])

    def test_a_failed_or_pending_order_can_be_tried_again(self) -> None:
        for status in ("failed", "pending"):
            self.order(order_id=f"o_{status}", status=status)
            response = self.client.get(f"/api/transactions/razorpay/orders/o_{status}")
            self.assertEqual(200, response.status_code, status)

    def subscription(self, *players: Player) -> RazorpayTransaction:
        plan = SubscriptionPlan.objects.filter(season=Season.objects.get(name="Season 2026-2027"))[
            0
        ]
        transaction = self.order(type="annual-subscription", event=None)
        for player in players:
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction, player=player, plan=plan, amount=100
            )
        self.plan = plan
        return transaction

    def description(self) -> str:
        response = self.client.get("/api/transactions/razorpay/orders/order_1")
        self.assertEqual(200, response.status_code, response.content)
        return str(response.json()["description"])

    def test_a_single_subscription_names_tier_member_and_season(self) -> None:
        self.subscription(self.player)
        self.assertEqual(
            f"{self.plan.type.name.removesuffix(' Subscription')} subscription "
            f"for John Williamson, {self.plan.season.name}",
            self.description(),
        )

    def test_a_tier_called_subscription_does_not_say_it_twice(self) -> None:
        self.subscription(self.player)
        self.assertTrue(self.plan.type.name.endswith(" Subscription"))
        self.assertNotIn("ubscription subscription", self.description())

    def test_a_group_subscription_names_everyone(self) -> None:
        other = create_player(
            User.objects.create(username="z@foo.com", first_name="Zed", last_name="Zee")
        )
        self.subscription(self.player, other)
        self.assertEqual(
            "Subscription group payment by John Williamson for John Williamson, Zed Zee",
            self.description(),
        )

    def test_a_form_payment_names_the_form(self) -> None:
        transaction = self.order(type="form-payment", event=None)
        form = Form.objects.create(title="Camp Form", slug="camp-form", fields=[])
        FormResponse.objects.create(form=form, user=self.user, answers={}, transaction=transaction)
        self.assertEqual("Payment by John Williamson for form: Camp Form", self.description())

    def lines(self) -> list[dict[str, Any]]:
        response = self.client.get("/api/transactions/razorpay/orders/order_1")
        self.assertEqual(200, response.status_code, response.content)
        return list(response.json()["lines"])

    def test_a_group_subscription_lists_each_tier_with_its_people(self) -> None:
        other = create_player(
            User.objects.create(username="z@foo.com", first_name="Zed", last_name="Zee")
        )
        transaction = self.subscription(self.player, other)
        transaction.amount = 200
        transaction.save()
        [line] = self.lines()
        self.assertEqual(f"{self.plan.type.name}, {self.plan.season.name}", line["particulars"])
        self.assertEqual(["John Williamson", "Zed Zee"], sorted(line["people"]))
        self.assertEqual((2, 100, 200), (line["quantity"], line["rate"], line["amount"]))

    def test_a_player_registration_splits_out_the_late_fee(self) -> None:
        transaction = self.order(
            amount=1200,
            notes={"base_amount": "1000", "penalty_amount": "200", "days_late": "3"},
        )
        RazorpayTransactionPlayer.objects.create(transaction=transaction, player=self.player)
        fee, late = self.lines()
        self.assertEqual("Player fee, NCS Sectionals 2023", fee["particulars"])
        self.assertEqual(["John Williamson"], fee["people"])
        self.assertEqual((1, 1000, 1000), (fee["quantity"], fee["rate"], fee["amount"]))
        self.assertEqual("Late fee, 3 days late", late["particulars"])
        self.assertEqual(200, late["amount"])

    def test_a_team_registration_names_the_team(self) -> None:
        team = Team.objects.create(name="Bangalore Hustle", slug="hustle")
        self.order(type="team-reg", team=team, notes={"base_amount": "50000"})
        [line] = self.lines()
        self.assertEqual("Team fee, NCS Sectionals 2023", line["particulars"])
        self.assertEqual((["Bangalore Hustle"], 50000), (line["people"], line["amount"]))

    def test_a_form_payment_is_one_line(self) -> None:
        transaction = self.order(type="form-payment", event=None)
        form = Form.objects.create(title="Camp Form", slug="camp-form", fields=[])
        FormResponse.objects.create(form=form, user=self.user, answers={}, transaction=transaction)
        [line] = self.lines()
        self.assertEqual(("Form: Camp Form", 50000), (line["particulars"], line["amount"]))

    def test_one_day_late_is_said_once(self) -> None:
        transaction = self.order(
            amount=1100,
            notes={"base_amount": "1000", "penalty_amount": "100", "days_late": "1"},
        )
        RazorpayTransactionPlayer.objects.create(transaction=transaction, player=self.player)
        self.assertEqual("Late fee, 1 day late", self.lines()[1]["particulars"])

    def test_an_uneven_split_has_no_rate(self) -> None:
        team = Team.objects.create(name="Bangalore Hustle", slug="hustle")
        self.order(type="team-reg", team=team, amount=50000, notes={"base_amount": "50000"})
        other = create_player(User.objects.create(username="z@foo.com", first_name="Zed"))
        transaction = self.order(
            order_id="order_2",
            amount=1001,
            notes={"base_amount": "1001", "penalty_amount": "0"},
        )
        for player in (self.player, other):
            RazorpayTransactionPlayer.objects.create(transaction=transaction, player=player)
        body = self.client.get("/api/transactions/razorpay/orders/order_2").json()
        [line] = body["lines"]
        self.assertEqual((2, None, 1001), (line["quantity"], line["rate"], line["amount"]))

    def test_only_a_subscription_promises_a_receipt(self) -> None:
        self.subscription(self.player)
        self.order(order_id="order_2")
        self.assertTrue(
            self.client.get("/api/transactions/razorpay/orders/order_1").json()["issues_receipt"]
        )
        self.assertFalse(
            self.client.get("/api/transactions/razorpay/orders/order_2").json()["issues_receipt"]
        )

    def test_the_pay_link_points_at_the_hub_pay_page(self) -> None:
        self.assertEqual(f"{settings.PUBLIC_URL}/pay/order_1", pay_link("order_1"))

    def test_lines_that_do_not_add_up_fall_back_to_the_description(self) -> None:
        self.order(notes={"base_amount": "100"})
        [line] = self.lines()
        self.assertEqual(
            "Player registration payment by John Williamson for , event: NCS Sectionals 2023",
            line["particulars"],
        )
        self.assertEqual(50000, line["amount"])
