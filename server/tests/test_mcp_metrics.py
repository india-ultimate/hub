import datetime
from typing import Any
from unittest import mock

from server.core.models import Player, Team
from server.mcp.tools import metrics
from server.subscription.models import Subscription
from server.tests.base import create_event
from server.tests.test_mcp_staff import StaffTestCase
from server.tournament.models import Registration
from server.transaction.models import RazorpayRefund, RazorpayTransaction

DONE = RazorpayTransaction.TransactionStatusChoices.COMPLETED


class TestMetrics(StaffTestCase):
    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch("server.mcp.tools.metrics.today", return_value=self.season.start_date)
        patcher.start()
        self.addCleanup(patcher.stop)

    def metric(self, name: str, **extra: Any) -> dict[str, Any]:
        got: dict[str, Any] = self.data("get_metrics", {"metric": name, **extra})
        self.assertTrue(got["definition"])
        self.assertTrue(got["coverage"])
        return got

    def groups(self, got: dict[str, Any]) -> dict[str, Any]:
        return {g["group"]: g["count"] for g in got["groups"]}

    def members(self, count: int, **player: Any) -> None:
        tag = len(Player.objects.all())
        for n in range(count):
            member = self.player(f"m{tag}-{n}@example.com", first="M", last=f"{tag}-{n}")
            for field, value in player.items():
                setattr(member, field, value)
            member.save()
            self.subscribe(member)

    def test_groups_under_five_show_as_a_floor(self) -> None:
        self.members(5, state_ut="KA")
        self.members(4, state_ut="MH")

        counts = self.groups(self.metric("members", group_by="state"))

        self.assertEqual({"Karnataka": 5, "Maharashtra": "<5"}, counts)

    def test_members_by_tier_gender_and_age_band(self) -> None:
        self.members(6, gender="F", date_of_birth=datetime.date(2010, 1, 1))
        self.members(5, gender="M", date_of_birth=datetime.date(1990, 1, 1))

        self.assertEqual({"Regular Subscription": 11}, self.groups(self.metric("members")))
        self.assertEqual(
            {"Female": 6, "Male": 5}, self.groups(self.metric("members", group_by="gender"))
        )
        self.assertEqual(
            {"Under 18": 6, "35 and over": 5},
            self.groups(self.metric("members", group_by="age_band")),
        )

    def test_inactive_and_refunded_members_are_not_counted(self) -> None:
        self.members(5)
        Subscription.objects.filter(player__user__email__startswith="m0-0").update(is_active=False)

        self.assertEqual({"Regular Subscription": "<5"}, self.groups(self.metric("members")))

    def test_renewals(self) -> None:
        for n in range(6):
            member = self.player(f"r{n}@example.com", last=f"R{n}")
            self.subscribe(member, self.last)
            if n < metrics.SMALL:
                self.subscribe(member)

        counts = self.groups(self.metric("renewals"))

        self.assertEqual("<5", counts["Not renewed yet (members last season only)"])
        self.assertEqual(5, counts["Renewed (members last season and this)"])
        self.assertEqual("<5", counts["New (members this season only)"])

    def test_revenue_is_net_of_processed_refunds_and_hides_small_groups(self) -> None:
        mira = self.player("mira@example.com")
        orders = [
            self.order(f"s{n}", mira, amount=100000, status=DONE, type="annual-subscription")
            for n in range(5)
        ]
        self.order("t1", mira, amount=50000, type="team-reg")
        RazorpayRefund.objects.create(
            transaction=orders[0], amount=25000, status=RazorpayRefund.Status.PROCESSED
        )
        RazorpayRefund.objects.create(
            transaction=orders[1], amount=99999, status=RazorpayRefund.Status.FAILED
        )
        RazorpayTransaction.objects.update(
            payment_date=datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
        )

        got = self.metric("revenue")

        by_name = {g["group"]: g for g in got["groups"]}
        self.assertEqual(
            {
                "group": "Annual Subscription",
                "orders": 5,
                "amount_paise": 475000,
                "amount": "₹4,750",
            },
            by_name["Annual Subscription"],
        )
        self.assertEqual(
            {"group": "Team Registration", "orders": "<5", "amount_paise": None, "amount": "<5"},
            by_name["Team Registration"],
        )

    def test_checkout_funnel(self) -> None:
        mira = self.player("mira@example.com")
        for n in range(5):
            self.order(f"f{n}", mira, status="failed")
        self.order("p1", mira, status="pending")
        RazorpayTransaction.objects.update(
            payment_date=datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
        )

        self.assertEqual(
            {"Failed": 5, "Pending": "<5"}, self.groups(self.metric("checkout_funnel"))
        )

    def test_registrations_by_event_top_twenty(self) -> None:
        team = Team.objects.create(name="T", ultimate_central_id=1)
        busy = create_event("Busy")
        quiet = create_event("Quiet")
        for event, count in ((busy, 5), (quiet, 2)):
            event.start_date = datetime.date(2026, 11, 1)
            event.slug = event.title.lower()
            event.save()
            for n in range(count):
                Registration.objects.create(
                    event=event, team=team, player=self.player(f"{event.slug}{n}@example.com")
                )

        got = self.metric("registrations")

        self.assertEqual({"Busy": 5, "Quiet": "<5"}, self.groups(got))
        self.assertEqual("busy", got["groups"][0]["event_slug"])

    def test_it_is_a_fixed_allowlist_and_staff_only(self) -> None:
        self.assertTrue(self.call("get_metrics", {"metric": "everything"})["isError"])
        self.assertTrue(
            self.call("get_metrics", {"metric": "members", "group_by": "email"})["isError"]
        )
        self.assertTrue(
            self.call("get_metrics", {"metric": "members", "season_slug": "x"})["isError"]
        )

    def test_age_bands(self) -> None:
        self.assertEqual(
            ["Under 18", "18 to 24", "25 to 34", "35 and over"],
            [metrics._band(a) for a in (17.9, 20, 30, 40)],
        )
