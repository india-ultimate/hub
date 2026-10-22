import json
from typing import Any
from unittest import mock

from django.test import RequestFactory, override_settings
from django.utils.timezone import now

from server.core.models import Guardianship, Player, User
from server.mcp.dispatch import ApiResponse
from server.mcp.registry import ToolContext
from server.mcp.tools import membership
from server.receipts.models import Receipt
from server.receipts.rows import group
from server.season.models import Season
from server.servicerequests.models import ServiceRequest, ServiceRequestType
from server.subscription.models import (
    SponsorshipGrant,
    Subscription,
    SubscriptionPlan,
    SubscriptionType,
)
from server.tests.base import fake_order
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer

HUB = "https://hub.example.org"
CREATE_ORDER = "server.transaction.client.razorpay.create_order"


class MembershipCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.season = Season.objects.get(name="Season 2026-2027")
        self.me = self.make_player(self.user)
        ward_user = User.objects.create(username="w@x.com", first_name="Wren", last_name="Rao")
        self.ward = self.make_player(ward_user)
        Guardianship.objects.create(user=self.user, player=self.ward, relation="MO")
        stranger = User.objects.create(
            username="s@x.com", email="s@x.com", first_name="Sam", last_name="Roe", phone="999"
        )
        self.stranger = self.make_player(stranger)

    @staticmethod
    def make_player(user: User) -> Player:
        return Player.objects.create(user=user, date_of_birth="2000-01-01", city="Pune")

    def quote(self, items: list[dict[str, Any]]) -> tuple[Season, list[dict[str, Any]]]:
        quoted = membership.quote_items(items)
        if isinstance(quoted, str):
            self.fail(quoted)
        return quoted

    def price(self, slug: str) -> int:
        return SubscriptionPlan.objects.get(season=self.season, type__slug=slug).amount

    def hold(self, player: Player, slug: str, paid: int | None = None) -> None:
        plan = SubscriptionPlan.objects.get(season=self.season, type__slug=slug)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=plan,
            is_active=True,
            amount_paid=plan.amount if paid is None else paid,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )


@override_settings(PUBLIC_URL=HUB)
class TestGetMembershipOptions(MembershipCase):
    def options(self, arguments: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        result = self.call("get_membership_options", arguments or {})
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        players: list[dict[str, Any]] = result["structuredContent"]["players"]
        return players

    def test_it_is_a_read_tool(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}
        self.assertTrue(listed["get_membership_options"]["annotations"]["readOnlyHint"])

    def test_defaults_to_self_and_wards_with_prices(self) -> None:
        players = self.options()
        self.assertEqual([self.me.id, self.ward.id], [p["player_id"] for p in players])
        mine = players[0]
        self.assertEqual("Asha Rao", mine["full_name"])
        self.assertIsNone(mine["current_tier"])
        regular = next(o for o in mine["options"] if o["tier"] == "regular")
        self.assertEqual(self.price("regular"), regular["amount_paise"])
        self.assertTrue(regular["amount"].startswith("₹"))
        self.assertEqual("new", regular["kind"])
        self.assertFalse(regular["needs_grant"])

    def test_a_stranger_shows_only_the_name_and_prices(self) -> None:
        self.hold(self.stranger, "community")
        [stranger] = self.options({"player_ids": [self.stranger.id]})
        self.assertEqual(
            {"player_id", "full_name", "options", "not_available_reason"}, set(stranger)
        )
        self.assertEqual("Sam Roe", stranger["full_name"])
        text = json.dumps(stranger)
        for private in ("s@x.com", "999", "Pune", "2000"):
            self.assertNotIn(private, text)
        self.assertTrue(stranger["options"])

    def test_an_upgrade_costs_the_difference(self) -> None:
        self.hold(self.me, "community")
        [mine] = self.options({"player_ids": [self.me.id]})
        self.assertEqual(SubscriptionType.objects.get(slug="community").name, mine["current_tier"])
        regular = next(o for o in mine["options"] if o["tier"] == "regular")
        self.assertEqual("upgrade", regular["kind"])
        self.assertEqual(self.price("regular") - self.price("community"), regular["amount_paise"])
        self.assertNotIn("community", [o["tier"] for o in mine["options"]])

    def test_the_sponsored_tier_needs_a_grant(self) -> None:
        sponsored = SubscriptionType.objects.get(requires_grant=True).slug
        [mine] = self.options({"player_ids": [self.me.id]})
        offer = next(o for o in mine["options"] if o["tier"] == sponsored)
        self.assertTrue(offer["needs_grant"])
        SponsorshipGrant.objects.create(player=self.me, season=self.season)
        [mine] = self.options({"player_ids": [self.me.id]})
        offer = next(o for o in mine["options"] if o["tier"] == sponsored)
        self.assertFalse(offer["needs_grant"])

    def test_a_grant_tier_over_a_lower_one_is_an_upgrade(self) -> None:
        cheap = 10000
        SubscriptionPlan.objects.filter(season=self.season, type__slug="community").update(
            amount=cheap
        )
        self.hold(self.me, "community")
        sponsored = SubscriptionType.objects.get(requires_grant=True)
        plan = SubscriptionPlan.objects.get(season=self.season, type=sponsored)
        [mine] = self.options({"player_ids": [self.me.id]})
        offer = next(o for o in mine["options"] if o["tier"] == sponsored.slug)
        self.assertEqual(("upgrade", plan.amount - cheap), (offer["kind"], offer["amount_paise"]))

    def test_the_top_tier_has_nothing_to_buy(self) -> None:
        patron = SubscriptionPlan.objects.filter(season=self.season).order_by("-amount")[0]
        self.hold(self.me, patron.type.slug)
        [mine] = self.options({"player_ids": [self.me.id]})
        self.assertEqual([], mine["options"])
        self.assertIn("up a tier", mine["not_available_reason"])

    def test_an_unknown_player_is_an_error(self) -> None:
        self.assertTrue(self.call("get_membership_options", {"player_ids": [999999]})["isError"])


@override_settings(PUBLIC_URL=HUB)
class TestBuyMembership(MembershipCase):
    def buy(self, items: list[dict[str, Any]], confirmation: str | None = None) -> dict[str, Any]:
        arguments: dict[str, Any] = {"items": items}
        if confirmation:
            arguments["confirmation"] = confirmation
        return self.call("buy_membership", arguments)

    def confirmed(self, items: list[dict[str, Any]], amount: int) -> dict[str, Any]:
        asked = self.buy(items)
        self.assertFalse(asked["isError"], asked)
        data = asked["structuredContent"]
        self.assertFalse(data["done"])
        self.assertEqual(0, RazorpayTransaction.objects.count())
        with mock.patch(CREATE_ORDER, return_value=fake_order(amount)):
            return self.buy(items, data["confirmation"])

    def test_it_is_a_money_write(self) -> None:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}
        self.assertFalse(listed["buy_membership"]["annotations"]["readOnlyHint"])

    def test_the_question_names_people_and_total_and_makes_no_order(self) -> None:
        asked = self.buy([{"player_id": self.ward.id, "tier": "regular"}])
        question = asked["structuredContent"]["needs_confirmation"]
        self.assertIn("Wren Rao", question)
        self.assertIn("₹", question)
        self.assertEqual(0, RazorpayTransaction.objects.count())

    def test_an_order_is_made_only_after_the_yes(self) -> None:
        total = self.price("regular")
        result = self.confirmed([{"player_id": self.ward.id, "tier": "regular"}], total)
        self.assertFalse(result["isError"], result)
        data = result["structuredContent"]
        order = RazorpayTransaction.objects.get()
        self.assertEqual(order.order_id, data["order_id"])
        self.assertEqual(total, data["amount_paise"])
        self.assertEqual(f"{HUB}/pay/{order.order_id}", data["pay_url"])
        self.assertEqual(self.user, order.user)
        self.assertEqual([self.ward], list(order.players.all()))
        self.assertNotIn("id", self.keys(data))

    def test_an_order_already_waiting_to_be_paid_is_mentioned(self) -> None:
        order = RazorpayTransaction.objects.create(
            order_id="order_unpaid",
            amount=100,
            currency="INR",
            status="created",
            user=self.user,
            season=self.season,
        )
        RazorpayTransactionPlayer.objects.create(transaction=order, player=self.me)

        asked = self.buy([{"player_id": self.me.id, "tier": "regular"}])["structuredContent"]

        self.assertIn("already has a membership order waiting", asked["needs_confirmation"])

    def test_anyone_may_buy_for_anyone_and_a_group_is_one_order(self) -> None:
        items = [
            {"player_id": self.me.id, "tier": "regular"},
            {"player_id": self.stranger.id, "tier": "community"},
        ]
        total = self.price("regular") + self.price("community")
        result = self.confirmed(items, total)
        self.assertFalse(result["isError"], result)
        self.assertEqual(total, RazorpayTransaction.objects.get().amount)

    def test_an_upgrade_is_priced_as_the_difference(self) -> None:
        self.hold(self.stranger, "community")
        items = [{"player_id": self.stranger.id, "tier": "regular"}]
        result = self.confirmed(items, self.price("regular") - self.price("community"))
        self.assertFalse(result["isError"], result)
        self.assertEqual(
            self.price("regular") - self.price("community"),
            result["structuredContent"]["amount_paise"],
        )

    def test_upgrades_go_one_person_at_a_time(self) -> None:
        self.hold(self.stranger, "community")
        result = self.buy(
            [
                {"player_id": self.stranger.id, "tier": "regular"},
                {"player_id": self.me.id, "tier": "regular"},
            ]
        )
        self.assertTrue(result["isError"])
        self.assertIn("one person at a time", result["structuredContent"]["message"])

    def test_a_tier_that_needs_a_grant_is_refused_before_asking(self) -> None:
        sponsored = SubscriptionType.objects.get(requires_grant=True).slug
        result = self.buy([{"player_id": self.me.id, "tier": sponsored}])
        self.assertTrue(result["isError"])
        self.assertIn("approved", result["structuredContent"]["message"])
        self.assertEqual(0, RazorpayTransaction.objects.count())

    def test_a_price_that_moved_makes_no_order(self) -> None:
        items = [{"player_id": self.me.id, "tier": "regular"}]
        state = self.buy(items)["structuredContent"]["confirmation"]
        SubscriptionPlan.objects.filter(season=self.season, type__slug="regular").update(
            amount=self.price("regular") + 10000
        )
        with mock.patch(CREATE_ORDER) as create_order:
            result = self.buy(items, state)
        self.assertTrue(result["structuredContent"]["needs_confirmation"].startswith("Something"))
        create_order.assert_not_called()
        self.assertEqual(0, RazorpayTransaction.objects.count())

    def test_the_action_requotes_even_when_the_binding_matches(self) -> None:
        items = [{"player_id": self.me.id, "tier": "regular"}]
        season, lines = self.quote(items)
        total = self.price("regular")
        SubscriptionPlan.objects.filter(season=self.season, type__slug="regular").update(
            amount=total + 10000
        )
        outer = RequestFactory().get("/mcp")
        ctx = ToolContext(
            self.user, mock.MagicMock(), True, {}, None, None, "buy_membership", outer
        )
        with mock.patch(CREATE_ORDER) as create_order:
            result = membership.place_order(ctx, season, lines, total)
        self.assertTrue(result.is_error)
        self.assertIn("₹", result.data["message"])
        create_order.assert_not_called()

    def test_a_line_that_changed_is_refused_though_the_total_matches(self) -> None:
        items = [
            {"player_id": self.me.id, "tier": "regular"},
            {"player_id": self.stranger.id, "tier": "community"},
        ]
        season, lines = self.quote(items)
        ctx = ToolContext(
            self.user,
            mock.MagicMock(),
            True,
            {},
            None,
            None,
            "buy_membership",
            RequestFactory().get("/"),
        )
        moved = [
            {**lines[0], "amount_paise": lines[0]["amount_paise"] + 1000},
            {**lines[1], "amount_paise": lines[1]["amount_paise"] - 1000},
        ]
        total = sum(line["amount_paise"] for line in lines)
        with mock.patch(CREATE_ORDER) as create_order:
            result = membership.place_order(ctx, season, moved, total)
        self.assertTrue(result.is_error)
        create_order.assert_not_called()

    def test_duplicate_and_empty_orders_are_refused(self) -> None:
        self.assertTrue(self.buy([])["isError"])
        twice = [{"player_id": self.me.id, "tier": "regular"}] * 2
        self.assertTrue(self.buy(twice)["isError"])

    def test_a_razorpay_outage_is_a_clean_failure(self) -> None:
        items = [{"player_id": self.me.id, "tier": "regular"}]
        state = self.buy(items)["structuredContent"]["confirmation"]
        with mock.patch(CREATE_ORDER, return_value=None):
            result = self.buy(items, state)
        self.assertTrue(result["isError"])
        self.assertEqual(0, RazorpayTransaction.objects.count())


@override_settings(PUBLIC_URL=HUB)
class TestListMyPayments(MembershipCase):
    def order(self, status: str, user: User | None = None) -> RazorpayTransaction:
        data = fake_order(5000)
        return RazorpayTransaction.objects.create(
            order_id=data["order_id"],
            status=status,
            amount=5000,
            currency="INR",
            payment_id="",
            payment_signature="SECRETSIG",
            notes={"user_id": 1, "secret": "SECRETNOTE"},
            user=user or self.user,
            season=self.season,
            type=RazorpayTransaction.TransactionTypeChoices.ANNUAL_SUBSCRIPTION,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )

    def payments(self, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.call("list_my_payments", arguments or {})
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        data: dict[str, Any] = result["structuredContent"]
        return data

    def test_unpaid_orders_carry_a_pay_link_and_paid_ones_do_not(self) -> None:
        unpaid = self.order("created")
        paid = self.order("completed")
        data = self.payments({"kind": "orders"})
        by_id = {o["order_id"]: o for o in data["orders"]}
        self.assertEqual(f"{HUB}/pay/{unpaid.order_id}", by_id[unpaid.order_id]["pay_url"])
        self.assertNotIn("pay_url", by_id[paid.order_id])
        self.assertEqual(5000, by_id[paid.order_id]["amount_paise"])
        self.assertEqual("₹50", by_id[paid.order_id]["amount"])

    def test_unpaid_orders_come_before_paid_ones(self) -> None:
        paid = self.order("completed")
        unpaid = self.order("created")

        data = self.payments({"kind": "orders"})

        self.assertEqual([unpaid.order_id, paid.order_id], [o["order_id"] for o in data["orders"]])

    def test_receipts_and_orders_are_trimmed_separately(self) -> None:
        receipts = [
            {
                "id": n,
                "number": f"R-{n}",
                "kind": "payment",
                "date": "2026-01-01",
                "summary": "x" * 200,
                "total": 5000,
                "original_id": None,
            }
            for n in range(300)
        ]
        orders = [
            {
                "order_id": f"order_{n}",
                "amount": 5000,
                "status": "completed",
                "type": "R",
                "players": ["Asha Rao"] * 10,
                "payment_date": "2026-01-01",
                "receipt_id": None,
            }
            for n in range(1000)
        ]

        def answer(ctx: Any, method: str, path: str, **kw: Any) -> ApiResponse:
            return ApiResponse(200, receipts if "receipts" in path else orders)

        with mock.patch("server.mcp.tools.membership.call_api", answer):
            data = self.payments()

        self.assertEqual(300, data["receipts_truncated"]["total"])
        self.assertEqual(1000, data["orders_truncated"]["total"])
        self.assertNotIn("truncated", data)

    def test_unpaid_lists_only_open_orders(self) -> None:
        unpaid = self.order("created")
        self.order("completed")
        self.order("failed")
        data = self.payments({"kind": "unpaid"})
        self.assertEqual([unpaid.order_id], [o["order_id"] for o in data["orders"]])
        self.assertNotIn("receipts", data)

    def test_secrets_are_stripped(self) -> None:
        self.order("created")
        text = json.dumps(self.payments())
        for secret in ("SECRETSIG", "SECRETNOTE", "payment_signature", "notes"):
            self.assertNotIn(secret, text)

    def test_an_order_someone_else_made_has_no_pay_link(self) -> None:
        other = self.order("created", user=self.stranger.user)
        Guardianship.objects.get(player=self.ward).delete()
        RazorpayTransaction.objects.filter(order_id=other.order_id).update(user=self.stranger.user)
        other_txn = other
        other_txn.players.add(self.me, through_defaults={"plan": None, "amount": 5000})
        data = self.payments({"kind": "orders"})
        [row] = data["orders"]
        self.assertNotIn("pay_url", row)

    def test_receipts_link_to_the_receipt_page(self) -> None:
        paid = self.order("completed")
        receipt = Receipt.objects.create(
            transaction=paid,
            number="R-1",
            sequence=1,
            financial_year="2026-27",
            issued_at=now(),
            payer_name="Asha Rao",
            order_id=paid.order_id,
            kind=Receipt.Kind.RECEIPT,
            total=5000,
            lines=group([("Membership", "Asha Rao", 5000, 1)]),
        )
        data = self.payments({"kind": "receipts"})
        [row] = data["receipts"]
        self.assertEqual(f"{HUB}/receipts/{receipt.pk}", row["receipt_url"])
        self.assertEqual(5000, row["total_paise"])
        self.assertEqual("₹50", row["total"])
        self.assertNotIn("orders", data)

    def test_a_bad_kind_is_refused(self) -> None:
        self.assertTrue(self.call("list_my_payments", {"kind": "gifts"})["isError"])


@override_settings(PUBLIC_URL=HUB)
class TestRequestSponsorship(MembershipCase):
    def ask(self, ids: list[int], confirmation: str | None = None) -> dict[str, Any]:
        arguments: dict[str, Any] = {"player_ids": ids, "message": "Student, cannot afford it"}
        if confirmation:
            arguments["confirmation"] = confirmation
        return self.call("request_sponsorship", arguments)

    def send(self, ids: list[int]) -> dict[str, Any]:
        state = self.ask(ids)["structuredContent"]["confirmation"]
        return self.ask(ids, state)

    def test_a_confirmed_request_is_filed_for_the_current_season(self) -> None:
        asked = self.ask([self.ward.id])
        self.assertEqual(0, ServiceRequest.objects.count())
        self.assertIn("Wren Rao", asked["structuredContent"]["needs_confirmation"])
        result = self.send([self.ward.id])
        self.assertFalse(result["isError"], result)
        request = ServiceRequest.objects.get()
        self.assertEqual(ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION, request.type)
        self.assertEqual(self.season, request.season)
        self.assertEqual([self.ward], list(request.service_players.all()))
        self.assertEqual("PENDING", result["structuredContent"]["status"])
        self.assertEqual(request.pk, result["structuredContent"]["request_id"])

    def test_a_duplicate_pending_request_is_refused(self) -> None:
        self.assertFalse(self.send([self.ward.id])["isError"])
        again = self.send([self.ward.id])
        self.assertTrue(again["isError"])
        self.assertIn("already", again["structuredContent"]["message"])
        self.assertEqual(1, ServiceRequest.objects.count())

    def test_the_route_refuses_the_duplicate_too(self) -> None:
        self.client.force_login(self.user)
        body = {
            "type": "REQUEST_SPONSORED_SUBSCRIPTION",
            "message": "please",
            "service_player_ids": [self.ward.id],
            "season_id": self.season.id,
        }
        first = self.client.post("/api/service-requests/", body, content_type="application/json")
        second = self.client.post("/api/service-requests/", body, content_type="application/json")
        self.assertEqual(200, first.status_code)
        self.assertEqual(400, second.status_code)
        self.assertIn("Wren Rao", second.json()["message"])

    def test_a_decided_request_does_not_block_a_new_one(self) -> None:
        self.assertFalse(self.send([self.ward.id])["isError"])
        ServiceRequest.objects.update(status="REJECTED")
        self.assertFalse(self.send([self.ward.id])["isError"])

    def test_a_pending_request_for_another_season_does_not_block(self) -> None:
        self.assertFalse(self.send([self.ward.id])["isError"])
        ServiceRequest.objects.update(season=Season.objects.get(name="Season 2025-2026"))
        self.assertFalse(self.send([self.ward.id])["isError"])

    def test_no_players_is_refused(self) -> None:
        self.assertTrue(
            self.call("request_sponsorship", {"player_ids": [], "message": "x"})["isError"]
        )
