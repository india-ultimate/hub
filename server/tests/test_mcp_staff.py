import datetime
import json
from typing import Any
from unittest import mock

from django.contrib.auth.models import Permission
from django.utils.timezone import now

from server.core.models import Player, User
from server.duplicates.players.models import ClusterMember, DuplicateCluster
from server.mcp.tools.staff_members import find_season, season_slug
from server.payment_account.models import PaymentAccount
from server.receipts.models import Receipt
from server.season.models import Season
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.servicerequests.service import approve_sponsorship, reject
from server.subscription.models import (
    SponsorshipGrant,
    Subscription,
    SubscriptionPlan,
    SubscriptionType,
)
from server.task.models import Task
from server.tests.base import create_event
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.ticket.models import Ticket, TicketMessage
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)

TODAY = datetime.date(2026, 10, 20)


class StaffTestCase(McpProtocolTestCase):
    def setUp(self) -> None:
        super().setUp()
        for target in ("server.season.models.today", "server.mcp.tools.staff_members.today"):
            patcher = mock.patch(target, return_value=TODAY)
            patcher.start()
            self.addCleanup(patcher.stop)
        make_token(self.user, "w", scope="hub:read hub:write")
        self.user.is_staff = True
        self.user.save()
        self.season = Season.objects.get(name="Season 2026-2027")
        self.last = Season.objects.get(name="Season 2025-2026")

    def data(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call(name, arguments)
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        return result["structuredContent"]

    def player(self, email: str, first: str = "Mira", last: str = "Das", phone: str = "") -> Player:
        user = User.objects.create(
            username=email, email=email, first_name=first, last_name=last, phone=phone
        )
        return Player.objects.create(user=user, date_of_birth="2000-01-01", city="Pune")

    def subscribe(
        self, player: Player, season: Season | None = None, **fields: Any
    ) -> Subscription:
        season = season or self.season
        plan = SubscriptionPlan.objects.get(
            season=season, type=SubscriptionType.objects.get(slug="regular")
        )
        values: dict[str, Any] = {
            "plan": plan,
            "is_active": True,
            "waiver_valid": True,
            "coc_agreed": True,
            "start_date": season.start_date,
            "end_date": season.end_date,
            "amount_paid": plan.amount,
        }
        return Subscription.objects.create(player=player, season=season, **{**values, **fields})

    def order(
        self, order_id: str, player: Player, amount: int = 75000, **fields: Any
    ) -> RazorpayTransaction:
        values: dict[str, Any] = {
            "payment_id": "pay_" + order_id,
            "amount": amount,
            "currency": "INR",
            "user": player.user,
            "season": self.season,
            "status": RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            "payment_signature": "sig-secret",
            "notes": {"secret": "note-secret"},
        }
        return RazorpayTransaction.objects.create(order_id=order_id, **{**values, **fields})


class TestAudience(StaffTestCase):
    TOOLS = [
        "find_member",
        "get_member_status",
        "lookup_payment",
        "get_staff_inbox",
        "get_membership_report",
        "list_service_requests",
        "decide_sponsorship_request",
        "get_metrics",
    ]

    def test_staff_see_the_tools(self) -> None:
        self.assertTrue(set(self.TOOLS) <= set(self.names(self.modern("tools/list"))))

    def test_others_neither_see_nor_call_them(self) -> None:
        self.user.is_staff = False
        self.user.save()

        self.assertFalse(set(self.TOOLS) & set(self.names(self.modern("tools/list"))))
        for name in self.TOOLS:
            with self.subTest(tool=name):
                response = self.modern("tools/call", {"name": name, "arguments": {}}).json()
                self.assertEqual(-32602, response["error"]["code"])

    def test_the_account_report_is_for_viewers_only(self) -> None:
        self.user.is_staff = False
        self.user.save()
        self.assertNotIn("get_payment_account_report", self.names(self.modern("tools/list")))
        account = PaymentAccount.objects.create(name="Assoc", slug="assoc")
        account.viewers.add(self.user)
        self.assertIn("get_payment_account_report", self.names(self.modern("tools/list")))


class TestFindMember(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mira = self.player("mira@example.com", phone="+919812345678")
        self.mira.iu_id = "IU-77"
        self.mira.save()
        self.player("other@example.com", first="Zed", last="Roe")

    def test_matches_name_email_phone_and_iu_id(self) -> None:
        for query in ("Mira Das", "mira@exa", "5678", "IU-77"):
            with self.subTest(query=query):
                members = self.data("find_member", {"query": query})["members"]
                self.assertEqual([self.mira.pk], [m["player_id"] for m in members])

    def test_gives_names_and_ids_but_no_contact_details(self) -> None:
        result = self.call("find_member", {"query": "mira@example.com"})

        (member,) = result["structuredContent"]["members"]
        self.assertEqual({"player_id", "user_id", "full_name", "iu_id", "city"}, set(member))
        self.assertNotIn("mira@", json.dumps(result))
        self.assertNotIn("5678", json.dumps(result))

    def test_at_most_ten(self) -> None:
        for n in range(12):
            self.player(f"bulk{n}@example.com", first="Bulk", last=str(n))

        self.assertEqual(10, len(self.data("find_member", {"query": "Bulk"})["members"]))


class TestGetMemberStatus(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mira = self.player("mira@example.com")

    def status(self, **extra: Any) -> Any:
        return self.data("get_member_status", {"player_id": self.mira.pk, **extra})

    def test_no_membership_this_season(self) -> None:
        got = self.status()

        self.assertFalse(got["is_active"])
        self.assertEqual(["No membership for Season 2026-2027."], got["why_not_active"])

    def test_active_member_has_no_reasons_and_both_seasons_listed(self) -> None:
        self.subscribe(self.mira)
        self.subscribe(self.mira, self.last, is_active=False)

        got = self.status()

        self.assertTrue(got["is_active"])
        self.assertEqual([], got["why_not_active"])
        self.assertEqual(
            ["season-2026-2027", "season-2025-2026"],
            [s["season_slug"] for s in got["subscriptions"]],
        )

    def test_expired(self) -> None:
        self.subscribe(self.mira, is_active=False, end_date=datetime.date(2026, 9, 1))

        self.assertEqual(
            ["The membership expired on 01 Sep 2026."], self.status()["why_not_active"]
        )

    def test_waiver_and_coc_missing(self) -> None:
        self.subscribe(self.mira, waiver_valid=False, coc_agreed=False)

        got = self.status()

        self.assertFalse(got["is_active"])
        self.assertEqual(
            ["The waiver is not signed.", "The code of conduct is not agreed."],
            got["why_not_active"],
        )

    def test_refunded(self) -> None:
        self.subscribe(self.mira, is_active=False, refunded_at=now())

        self.assertIn("was refunded on", self.status()["why_not_active"][0])

    def test_lines_refunds_grant_and_secrets(self) -> None:
        txn = self.order("order_1", self.mira)
        line = RazorpayTransactionPlayer.objects.create(
            transaction=txn,
            player=self.mira,
            amount=75000,
            needs_review=True,
            review_note="Paid twice",
        )
        RazorpayRefund.objects.create(
            transaction=txn,
            line=line,
            amount=75000,
            status=RazorpayRefund.Status.FAILED,
            error="Insufficient balance",
            reason="duplicate",
        )
        SponsorshipGrant.objects.create(player=self.mira, season=self.season)

        got = self.status()

        (shown,) = got["payment_lines"]
        self.assertEqual(
            (True, "Paid twice", 75000, "₹750"),
            (shown["needs_review"], shown["review_note"], shown["amount_paise"], shown["amount"]),
        )
        self.assertEqual("Insufficient balance", got["refunds"][0]["error"])
        self.assertTrue(got["sponsorship_granted"])
        self.assertNotIn("sig-secret", json.dumps(got))
        self.assertNotIn("note-secret", json.dumps(got))

    def test_eligibility_for_an_event(self) -> None:
        event = create_event("Nationals")
        event.slug = "nationals"
        event.save()

        with mock.patch(
            "server.mcp.tools.staff_members.eligibility.check",
            return_value={"message": "Waiver not signed"},
        ):
            got = self.status(event_slug="nationals")

        self.assertEqual(
            {"event_slug": "nationals", "can_play": False, "reason": "Waiver not signed"},
            got["eligibility"],
        )
        self.assertTrue(
            self.call("get_member_status", {"player_id": 1, "event_slug": "nope"})["isError"]
        )

    def test_documents_give_presence_never_files(self) -> None:
        self.subscribe(self.mira)

        docs = self.status()["documents"]

        self.assertEqual({"present": False, "expiry": None, "active": False}, docs["college_id"])
        self.assertTrue(docs["waiver_valid"])
        self.assertNotIn("http", json.dumps(docs))

    def test_unknown_player(self) -> None:
        self.assertTrue(self.call("get_member_status", {"player_id": 99999})["isError"])


class TestLookupPayment(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mira = self.player("mira@example.com")
        self.txn = self.order("order_1", self.mira)
        self.line = RazorpayTransactionPlayer.objects.create(
            transaction=self.txn, player=self.mira, amount=75000
        )

    def test_by_order_payment_and_email(self) -> None:
        for args in (
            {"order_id": "order_1"},
            {"payment_id": "pay_order_1"},
            {"email": "MIRA@example.com"},
        ):
            with self.subTest(args=args):
                (payment,) = self.data("lookup_payment", args)["payments"]
                self.assertEqual("order_1", payment["order_id"])

    def test_needs_exactly_one_key(self) -> None:
        self.assertTrue(self.call("lookup_payment", {})["isError"])
        self.assertTrue(
            self.call("lookup_payment", {"order_id": "a", "payment_id": "b"})["isError"]
        )

    def test_lines_receipts_refunds_flags_and_links(self) -> None:
        self.line.needs_review = True
        self.line.save()
        RazorpayRefund.objects.create(
            transaction=self.txn, amount=100, status=RazorpayRefund.Status.FAILED, error="boom"
        )
        Receipt.objects.create(
            kind="receipt",
            transaction=self.txn,
            number="R/1",
            financial_year="2026-27",
            sequence=1,
            issued_at=now(),
            payer_name="Mira Das",
            lines=[],
            total=75000,
        )

        (payment,) = self.data("lookup_payment", {"order_id": "order_1"})["payments"]

        self.assertEqual(["A line needs review", "A refund failed"], payment["flags"])
        self.assertEqual(75000, payment["amount_paise"])
        self.assertEqual("₹750", payment["amount"])
        self.assertEqual("R/1", payment["receipts"][0]["number"])
        self.assertEqual("boom", payment["refund_records"][0]["error"])
        links = payment["admin_links"]
        self.assertIn("/admin/refund-order/order_1/", links["refund_order"])
        self.assertIn(f"/admin/refund-line/{self.line.pk}/", links["refund_lines"][0]["url"])
        self.assertIn("/admin/server/razorpaytransaction/order_1/change/", links["transaction"])
        text = json.dumps(payment)
        self.assertNotIn("sig-secret", text)
        self.assertNotIn("note-secret", text)
        self.assertNotIn("mira@example.com", text)

    def test_at_most_ten(self) -> None:
        for n in range(12):
            self.order(f"extra_{n}", self.mira)

        self.assertEqual(
            10, len(self.data("lookup_payment", {"email": "mira@example.com"})["payments"])
        )

    def test_it_never_changes_anything(self) -> None:
        self.data("lookup_payment", {"order_id": "order_1"})

        self.assertEqual(0, RazorpayRefund.objects.count())


class TestStaffInbox(StaffTestCase):
    def test_empty(self) -> None:
        got = self.data("get_staff_inbox", {})

        self.assertEqual(
            {0},
            {section["count"] for section in got.values()},
        )

    def test_each_section_counts_and_links(self) -> None:
        mira = self.player("mira@example.com")
        ServiceRequest.objects.create(
            user=mira.user, type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION, message="help"
        )
        txn = self.order("order_1", mira)
        RazorpayTransactionPlayer.objects.create(
            transaction=txn, player=mira, amount=1, needs_review=True, review_note="odd"
        )
        RazorpayRefund.objects.create(
            transaction=txn, amount=5, status=RazorpayRefund.Status.FAILED, error="bad"
        )
        Ticket.objects.create(title="Stuck", description="d", created_by=mira.user)
        old = DuplicateCluster.objects.create()
        DuplicateCluster.objects.filter(pk=old.pk).update(
            created_at=now() - datetime.timedelta(days=8)
        )
        DuplicateCluster.objects.create()
        Task.objects.create(type="SEND_EMAIL", failed_at=now(), error="smtp down")
        Task.objects.create(
            type="SEND_EMAIL", failed_at=now() - datetime.timedelta(days=9), error="old"
        )

        got = self.data("get_staff_inbox", {})

        self.assertEqual(
            {
                "service_requests": 1,
                "lines_needing_review": 1,
                "failed_refunds": 1,
                "open_tickets": 1,
                "stale_duplicate_groups": 1,
                "failed_tasks": 1,
            },
            {name: section["count"] for name, section in got.items()},
        )
        for name, section in got.items():
            with self.subTest(section=name):
                self.assertTrue(section["oldest"][0]["url"].startswith("http"))
        self.assertEqual("Stuck", got["open_tickets"]["oldest"][0]["title"])

    def test_a_handled_ticket_is_not_listed_and_only_five_are_shown(self) -> None:
        mira = self.player("mira@example.com")
        handled = Ticket.objects.create(title="Done", description="d", created_by=mira.user)
        handled.assignees.add(self.user)
        TicketMessage.objects.create(ticket=handled, sender=self.user, message="on it")
        for n in range(7):
            Ticket.objects.create(title=f"T{n}", description="d", created_by=mira.user)

        tickets = self.data("get_staff_inbox", {})["open_tickets"]

        self.assertEqual(7, tickets["count"])
        self.assertEqual(5, len(tickets["oldest"]))
        self.assertNotIn("Done", [t["title"] for t in tickets["oldest"]])


class TestMembershipReport(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.kept = self.player("kept@example.com", first="Kay", last="Kept")
        self.lapsed = self.player("lapsed@example.com", first="Lee", last="Lapsed")
        self.new = self.player("new@example.com", first="Nia", last="New")
        self.subscribe(self.kept, self.last)
        self.subscribe(self.lapsed, self.last)
        self.subscribe(self.kept)
        self.subscribe(self.new, is_active=False)

    def report(self, kind: str, **extra: Any) -> Any:
        return self.data("get_membership_report", {"kind": kind, **extra})

    def test_active(self) -> None:
        got = self.report("active")

        self.assertEqual(1, got["count"])
        self.assertEqual(
            {"player_id": self.kept.pk, "full_name": "Kay Kept", "tier": "regular"}, got["rows"][0]
        )

    def test_not_renewed_is_last_season_minus_this_season(self) -> None:
        got = self.report("not_renewed")

        self.assertEqual([self.lapsed.pk], [r["player_id"] for r in got["rows"]])

    def test_a_refunded_membership_is_not_a_renewal(self) -> None:
        Subscription.objects.filter(player=self.kept, season=self.season).update(refunded_at=now())

        self.assertEqual(
            {self.kept.pk, self.lapsed.pk},
            {r["player_id"] for r in self.report("not_renewed")["rows"]},
        )

    def test_sponsored(self) -> None:
        granted = self.player("g@example.com", first="Gia", last="Granted")
        SponsorshipGrant.objects.create(player=granted, season=self.season)
        community = SubscriptionPlan.objects.get(
            season=self.season, type=SubscriptionType.objects.get(slug="community")
        )
        Subscription.objects.filter(player=self.kept, season=self.season).update(plan=community)
        SubscriptionType.objects.filter(slug="community").update(requires_grant=True)

        got = self.report("sponsored")

        self.assertEqual({self.kept.pk, granted.pk}, {r["player_id"] for r in got["rows"]})

    def test_check_emails(self) -> None:
        got = self.report("check_emails", emails=["KEPT@example.com", " ", "ghost@example.com"])

        self.assertEqual([self.kept.pk], [r["player_id"] for r in got["rows"]])
        self.assertEqual([3], got["not_active"])
        self.assertNotIn("ghost@", json.dumps(got))
        self.assertTrue(self.call("get_membership_report", {"kind": "check_emails"})["isError"])

    def test_another_season_and_a_bad_one(self) -> None:
        got = self.report("active", season_slug="season-2025-2026")

        self.assertEqual({self.kept.pk, self.lapsed.pk}, {r["player_id"] for r in got["rows"]})
        self.assertTrue(
            self.call("get_membership_report", {"kind": "active", "season_slug": "nope"})["isError"]
        )

    def test_rows_stop_at_200(self) -> None:
        for n in range(205):
            self.subscribe(self.player(f"m{n}@example.com", first="M", last=str(n)))

        got = self.report("active")

        self.assertEqual(206, got["count"])
        self.assertEqual(200, len(got["rows"]))

    def test_slug_round_trip(self) -> None:
        self.assertEqual(self.season, find_season(season_slug(self.season)))


class TestPaymentAccountReport(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account = PaymentAccount.objects.create(name="Assoc", slug="assoc")
        self.event = create_event("Nationals")
        self.event.slug = "nationals"
        self.event.save()
        self.mira = self.player("mira@example.com")
        self.order("o1", self.mira, event=self.event, account=self.account, type="player-reg")
        self.viewer = User.objects.create(username="v@x.com", email="v@x.com")
        self.account.viewers.add(self.viewer)
        make_token(self.viewer, "viewer", scope="hub:read")

    def test_a_viewer_gets_totals_and_masked_payers(self) -> None:
        result = self.call(
            "get_payment_account_report",
            {"account_slug": "assoc", "event_slug": "nationals"},
            bearer="viewer",
        )

        got = result["structuredContent"]
        self.assertFalse(result["isError"], result)
        self.assertEqual("nationals", got["event_slug"])
        self.assertEqual({"amount_paise": 75000, "amount": "₹750"}, got["totals"]["collected"])
        (row,) = got["payments"]
        self.assertEqual("o1", row["order_id"])
        self.assertNotIn("mira@example.com", json.dumps(got))
        self.assertNotIn("id", self.keys(got))

    def test_another_account_is_refused(self) -> None:
        PaymentAccount.objects.create(name="Other", slug="other")

        result = self.call("get_payment_account_report", {"account_slug": "other"}, bearer="viewer")

        self.assertTrue(result["isError"])

    def test_staff_see_any_account(self) -> None:
        got = self.data("get_payment_account_report", {"account_slug": "assoc"})

        self.assertEqual(1, got["count"])

    def test_unknown_event(self) -> None:
        result = self.call(
            "get_payment_account_report", {"account_slug": "assoc", "event_slug": "x"}
        )

        self.assertTrue(result["isError"])


class TestServiceRequests(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mira = self.player("mira@example.com")
        self.ward = self.player("ward@example.com", first="Wren", last="Das")
        self.sponsor = ServiceRequest.objects.create(
            user=self.mira.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="Please sponsor",
            season=self.season,
        )
        self.sponsor.service_players.add(self.mira, self.ward)

    def decide(self, decision: str, **extra: Any) -> dict[str, Any]:
        return self.call(
            "decide_sponsorship_request",
            {"request_id": self.sponsor.pk, "decision": decision, **extra},
            bearer="w",
        )

    def allow(self) -> None:
        self.user.user_permissions.add(Permission.objects.get(codename="change_servicerequest"))

    def test_lists_pending_with_players_and_message_apart(self) -> None:
        ServiceRequest.objects.create(
            user=self.mira.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="old",
            status=ServiceRequestStatus.APPROVED,
        )

        got = self.data("list_service_requests", {})
        everything = self.data("list_service_requests", {"status": "all"})

        (row,) = got["requests"]
        self.assertEqual(2, len(everything["requests"]))
        self.assertEqual("Please sponsor", row["message"])
        self.assertEqual({self.mira.pk, self.ward.pk}, {p["player_id"] for p in row["players"]})
        self.assertEqual("season-2026-2027", row["season_slug"])
        self.assertIn("/admin/server/servicerequest/", row["admin_url"])

    def test_a_merge_request_has_a_preview_without_contact_details(self) -> None:
        other = self.player("dup@example.com", first="Mira", last="Das")
        merge = ServiceRequest.objects.create(
            user=self.mira.user,
            type=ServiceRequestType.REQUEST_ACCOUNT_MERGE,
            message="same person",
        )
        cluster = DuplicateCluster.objects.create()
        member = ClusterMember.of(cluster, other.user)
        member.staff_request = merge
        member.save()

        got = self.data("list_service_requests", {})
        row = next(r for r in got["requests"] if r["request_id"] == merge.pk)

        labels = {line["label"] for line in row["merge_preview"]["compare"]}
        self.assertIn("Name", labels)
        self.assertFalse({"Email", "Phone", "Date of birth"} & labels)
        self.assertNotIn("dup@example.com", json.dumps(row["merge_preview"]))
        self.assertIsInstance(row["merge_preview"]["blockers"], list)

    def test_deciding_needs_the_permission(self) -> None:
        result = self.decide("approve")

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])

    def test_approving_asks_then_grants_and_emails(self) -> None:
        self.allow()

        asked = self.decide("approve")["structuredContent"]
        self.assertIn("Mira Das", asked["needs_confirmation"])
        self.assertIn("Wren Das", asked["needs_confirmation"])
        self.assertEqual(0, SponsorshipGrant.objects.count())
        with mock.patch("server.servicerequests.models.send_mail") as send:
            done = self.decide("approve", confirmation=asked["confirmation"])["structuredContent"]

        self.assertEqual("approved", done["status"])
        self.assertEqual({self.mira.pk, self.ward.pk}, set(done["player_ids"]))
        self.assertEqual(2, SponsorshipGrant.objects.filter(granted_by=self.user).count())
        self.assertEqual(1, send.call_count)
        self.sponsor.refresh_from_db()
        self.assertEqual(ServiceRequestStatus.APPROVED, self.sponsor.status)

    def test_rejecting_grants_nothing(self) -> None:
        self.allow()
        asked = self.decide("reject")["structuredContent"]

        done = self.decide("reject", confirmation=asked["confirmation"])["structuredContent"]

        self.assertEqual("rejected", done["status"])
        self.assertEqual(0, SponsorshipGrant.objects.count())

    def test_a_decided_request_cannot_be_decided_again(self) -> None:
        self.allow()
        self.sponsor.status = ServiceRequestStatus.REJECTED
        self.sponsor.save()

        self.assertTrue(self.decide("approve")["isError"])

    def test_a_merge_request_cannot_be_decided_here(self) -> None:
        self.allow()
        self.sponsor.type = ServiceRequestType.REQUEST_ACCOUNT_MERGE
        self.sponsor.save()

        self.assertTrue(self.decide("approve")["isError"])


class TestServiceFunctions(StaffTestCase):
    def test_approve_grants_with_the_approver_and_reject_does_not(self) -> None:
        mira = self.player("mira@example.com")
        item = ServiceRequest.objects.create(
            user=mira.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="x",
            season=self.season,
        )
        item.service_players.add(mira)

        season, players = approve_sponsorship(item, self.user)

        self.assertEqual((self.season, [mira]), (season, players))
        self.assertEqual(self.user, SponsorshipGrant.objects.get().granted_by)
        self.assertEqual(ServiceRequestStatus.APPROVED, item.status)
        reject(item)
        self.assertEqual(ServiceRequestStatus.REJECTED, item.status)
