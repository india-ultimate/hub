import datetime
import json
from typing import Any
from unittest import mock

from django.core import mail
from django.test import SimpleTestCase, override_settings
from razorpay.resources.order import Order

from server.core.models import Team, User
from server.mcp import registry
from server.mcp.dispatch import ApiResponse
from server.mcp.tools import team_registration
from server.registration.models import RosterEntry
from server.series.models import SeriesRosterInvitation
from server.subscription.models import Subscription
from server.tests.base import make_account
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.tests.test_payment_accounts import PLAYER_FEE, TEAM_FEE, razorpay_order
from server.tests.test_registration_state import StateTestCase
from server.tournament.models import Event, Registration, Tournament
from server.transaction.models import RazorpayTransaction
from server.utils import today


@override_settings(
    EMAIL_SECRET_KEY="test-invite-key",  # noqa: S106
    PUBLIC_URL="https://hub.test",
)
class Case(StateTestCase, McpProtocolTestCase):
    def setUp(self) -> None:
        StateTestCase.setUp(self)
        self.user = self.admin
        make_token(self.admin, "tok", scope="hub:read hub:write")
        self.addCleanup(self.restore_registry, dict(registry.TOOLS))
        self.args = {"event_slug": self.event.slug, "team_slug": self.team.slug}

    def player(self, email: str, *args: Any, **kw: Any) -> Any:
        player = super().player(email, *args, **kw)
        User.objects.filter(pk=player.user_id).update(first_name=email[0].upper(), last_name="Test")
        player.user.refresh_from_db()
        return player

    def read(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call(name, arguments)
        self.assertFalse(result["isError"], result)
        self.assertNotIn("id", self.keys(result["structuredContent"]))
        return result["structuredContent"]

    def confirmed(self, name: str, arguments: dict[str, Any], **after: Any) -> dict[str, Any]:
        asked = self.call(name, arguments)["structuredContent"]
        self.assertFalse(asked["done"])
        for change in after.values():
            change()
        return self.call(name, {**arguments, "confirmation": asked["confirmation"]})

    def asked(self, name: str, arguments: dict[str, Any]) -> str:
        return str(self.call(name, arguments)["structuredContent"]["needs_confirmation"])

    def order(self, amount: int) -> Any:
        return mock.patch.object(
            Order, "create", autospec=True, return_value=razorpay_order(amount)
        )


class TestGetTeamRegistration(Case):
    def test_says_who_is_ready_who_is_blocked_and_what_paying_costs(self) -> None:
        ready = self.player("a@x.com")
        blocked = self.player("w@x.com", waiver=False)
        data = self.read("get_team_registration", self.args)

        self.assertTrue(self.tool_is_read_only("get_team_registration"))
        self.assertFalse(data["all_set"])
        self.assertEqual("admin", data["viewer"])
        by_id = {p["player_id"]: p for p in data["players"]}
        self.assertEqual("ready", by_id[ready.id]["state_code"])
        self.assertEqual(
            {
                "by": "you",
                "tool": "pay_for_team",
                "label": by_id[ready.id]["text"],
                "arguments": {**self.args, "what": "roster"},
            },
            by_id[ready.id]["next_action"],
        )
        self.assertEqual("waiting.waiver", by_id[blocked.id]["state_code"])
        self.assertEqual("player", by_id[blocked.id]["next_action"]["by"])
        self.assertNotIn("arguments", by_id[blocked.id]["next_action"])
        self.assertEqual(
            {
                "ready_player_ids": [ready.id],
                "amount_paise": PLAYER_FEE,
                "amount": "₹1,000",
                "per_player": {"amount_paise": PLAYER_FEE, "amount": "₹1,000"},
                "held_by_other_admin_player_ids": [],
            },
            data["checkout"],
        )
        self.assertEqual({"amount_paise": TEAM_FEE, "amount": "₹5,000"}, data["team_fee"]["full"])
        self.assertEqual("roster", data["current_step"])
        self.assertIn("max_total", data["meter"])
        self.assertNotIn("href", json.dumps(data))
        self.assertNotIn("@x.com", json.dumps(data))

    def tool_is_read_only(self, name: str) -> bool:
        listed = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}
        return bool(listed[name]["annotations"]["readOnlyHint"] and listed[name]["title"])

    def test_a_plain_member_sees_the_status_without_admin_actions(self) -> None:
        member = self.player("m@x.com")
        self.player("b@x.com")
        make_token(member.user, "mtok", scope="hub:read")
        Team.objects.create(name="Elsewhere").admins.add(member.user)

        result = self.call("get_team_registration", self.args, "mtok")["structuredContent"]

        self.assertEqual("member", result["viewer"])
        self.assertIn("only its admins can change", result["note"])
        self.assertNotIn("checkout", result)
        self.assertNotIn("team_fee", result)
        self.assertNotIn("next_action", json.dumps(result))
        self.assertNotIn("next_tools", json.dumps(result))

    def test_a_stranger_gets_a_clear_miss(self) -> None:
        stranger = User.objects.create_user("s@x.com", "s@x.com", "pw")
        Team.objects.create(name="Elsewhere").admins.add(stranger)
        make_token(stranger, "stok", scope="hub:read")

        result = self.call("get_team_registration", self.args, "stok")

        self.assertTrue(result["isError"])
        self.assertIn("No registration page", result["structuredContent"]["message"])

    def test_a_bad_slug_is_refused(self) -> None:
        result = self.call("get_team_registration", {**self.args, "team_slug": "no way"})

        self.assertTrue(result["isError"])


class TestListTeamEvents(Case):
    def test_lists_the_event_with_where_it_stands(self) -> None:
        data = self.read("list_team_events", {})
        [row] = data["events"]
        self.assertEqual(
            (self.event.slug, self.team.slug, False),
            (row["event_slug"], row["team_slug"], row["all_set"]),
        )
        self.assertEqual(
            self.event.slug,
            self.read("list_team_events", {"team_slug": self.team.slug})["events"][0]["event_slug"],
        )

    def test_another_teams_slug_is_not_allowed(self) -> None:
        Team.objects.create(name="Other")
        result = self.call("list_team_events", {"team_slug": "other"})

        self.assertTrue(result["isError"])
        self.assertTrue(result["structuredContent"]["message"].startswith("Not allowed"))


class TestFindTeamCandidates(Case):
    def test_an_email_finds_one_player_and_says_adding_sends_an_invite(self) -> None:
        other = self.player("new@x.com", on_series=False, entry=False)
        data = self.read("find_team_candidates", {**self.args, "emails": ["new@x.com", "no@x.com"]})
        found, missing = data["results"]
        self.assertTrue(found["found"])
        self.assertEqual(other.id, found["candidates"][0]["player_id"])
        self.assertTrue(found["candidates"][0]["would_email_invite"])
        self.assertFalse(missing["found"])
        self.assertNotIn("new@x.com", json.dumps(found["candidates"]))

    def test_too_many_emails_are_refused(self) -> None:
        result = self.call("find_team_candidates", {**self.args, "emails": ["a@x.com"] * 21})

        self.assertTrue(result["isError"])

    def test_a_non_admin_is_denied(self) -> None:
        other = User.objects.create_user("o@x.com", "o@x.com", "pw")
        Team.objects.create(name="Elsewhere").admins.add(other)
        make_token(other, "otok", scope="hub:read")

        result = self.call("find_team_candidates", self.args, "otok")

        self.assertEqual(
            "Not allowed: Only team admins can change this roster",
            result["structuredContent"]["message"],
        )


class TestAddToRoster(Case):
    def test_the_preview_names_who_is_emailed_and_who_is_just_listed(self) -> None:
        listed = self.player("l@x.com", entry=False)
        invited = self.player("i@x.com", on_series=False, entry=False)

        message = self.asked("add_to_roster", {**self.args, "player_ids": [listed.id, invited.id]})

        self.assertIn(f"{invited.user.get_full_name()} will get an email", message)
        self.assertIn(f"{listed.user.get_full_name()} will just be listed", message)
        self.assertEqual([], mail.outbox)

    def test_adds_each_player_and_emails_only_the_invited(self) -> None:
        listed = self.player("l@x.com", entry=False)
        invited = self.player("i@x.com", on_series=False, entry=False)

        result = self.confirmed(
            "add_to_roster", {**self.args, "player_ids": [listed.id, invited.id]}
        )

        data = result["structuredContent"]
        self.assertTrue(data["done"], data)
        self.assertEqual([listed.id, invited.id], [p["player_id"] for p in data["players"]])
        self.assertEqual(
            2, RosterEntry.objects.filter(team=self.team, player__in=[listed, invited]).count()
        )
        self.assertEqual([invited.user.email], [m.to[0] for m in mail.outbox])
        self.assertTrue(SeriesRosterInvitation.objects.filter(to_player=invited).exists())

    def test_an_unknown_player_is_refused_before_asking(self) -> None:
        result = self.call("add_to_roster", {**self.args, "player_ids": [999999]})

        self.assertTrue(result["isError"])
        self.assertIn("No player with player_id 999999", json.dumps(result))

    def test_a_non_admin_is_denied(self) -> None:
        other = User.objects.create_user("o@x.com", "o@x.com", "pw")
        Team.objects.create(name="Elsewhere").admins.add(other)
        make_token(other, "otok", scope="hub:read hub:write")

        result = self.call("add_to_roster", {**self.args, "player_ids": [1]}, "otok")

        self.assertTrue(result["isError"])
        self.assertEqual([], mail.outbox)


class TestRemoveFromRoster(Case):
    def test_removes_an_unpaid_player(self) -> None:
        player = self.player("a@x.com")

        result = self.confirmed("remove_from_roster", {**self.args, "player_ids": [player.id]})

        self.assertTrue(result["structuredContent"]["done"])
        self.assertFalse(RosterEntry.objects.filter(player=player).exists())

    def test_a_paid_player_is_refused_with_the_way_to_change_it(self) -> None:
        paid = self.player("p@x.com", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=paid)
        free = self.player("f@x.com")

        result = self.confirmed(
            "remove_from_roster", {**self.args, "player_ids": [paid.id, free.id]}
        )

        data = result["structuredContent"]
        self.assertFalse(data["done"])
        self.assertEqual(1, data["failed"])
        self.assertEqual(
            "Already paid, or being paid: ask Hub to change it (create_ticket).",
            data["players"][0]["message"],
        )
        self.assertTrue(data["players"][1]["done"])
        self.assertTrue(Registration.objects.filter(player=paid).exists())


class TestResendRosterInvites(Case):
    def test_sends_a_fresh_invitation_by_email(self) -> None:
        player = self.player("i@x.com", on_series=False, entry=False)
        RosterEntry.objects.create(event=self.event, team=self.team, player=player)
        self.series.event_max_players_total = 5
        self.series.save()

        result = self.confirmed("resend_roster_invites", {**self.args, "player_ids": [player.id]})

        self.assertTrue(result["structuredContent"]["done"], result)
        self.assertEqual([player.user.email], [m.to[0] for m in mail.outbox])

    def test_it_is_counted_as_an_email_tool(self) -> None:
        self.assertTrue(registry.TOOLS["resend_roster_invites"].emails)
        self.assertTrue(registry.TOOLS["add_to_roster"].emails)


class TestPayForTeam(Case):
    def setUp(self) -> None:
        super().setUp()
        self.account = make_account()
        self.event.payment_account = self.account
        self.event.save()

    def test_roster_returns_a_pay_link_quoted_and_confirmed(self) -> None:
        self.player("a@x.com")
        self.player("b@x.com")
        args = {**self.args, "what": "roster"}

        message = self.asked("pay_for_team", args)
        with self.order(2 * PLAYER_FEE):
            result = self.confirmed("pay_for_team", args)

        self.assertIn("₹2,000", message)
        self.assertIn("20 minutes", message)
        data = result["structuredContent"]
        self.assertEqual(2 * PLAYER_FEE, data["amount_paise"])
        self.assertTrue(data["pay_url"].startswith("https://hub.test/pay/order_"))
        self.assertIn("20 minutes", data["message"])
        self.assertEqual(
            2, RosterEntry.objects.filter(team=self.team, held_by_order__isnull=False).count()
        )

    def test_a_roster_that_changes_before_the_yes_makes_no_order(self) -> None:
        stays = self.player("a@x.com")
        drops = self.player("b@x.com")

        def lose_waiver() -> None:
            Subscription.objects.filter(player=drops).update(waiver_valid=False)

        with self.order(PLAYER_FEE) as create:
            result = self.confirmed(
                "pay_for_team", {**self.args, "what": "roster"}, change=lose_waiver
            )

        data = result["structuredContent"]
        self.assertFalse(data["done"])
        self.assertTrue(data["needs_confirmation"].startswith("Something changed"))
        create.assert_not_called()
        self.assertFalse(RazorpayTransaction.objects.exists())
        self.assertIsNotNone(stays)

    def test_the_checkouts_409_reports_the_new_numbers(self) -> None:
        body = {
            "removed": [{"player_id": 3, "reason": "Needs a waiver"}],
            "old_amount": 200000,
            "new_amount": 100000,
        }

        result = team_registration._order(ApiResponse(409, body), 200000, "roster")

        self.assertTrue(result.is_error)
        self.assertEqual(100000, result.data["new_amount_paise"])
        self.assertEqual("₹1,000", result.data["new_amount"])
        self.assertEqual(body["removed"], result.data["removed"])

    def test_nobody_ready_is_explained(self) -> None:
        self.player("w@x.com", waiver=False)

        result = self.call("pay_for_team", {**self.args, "what": "roster"})

        self.assertTrue(result["isError"])
        self.assertIn("No players are ready", result["structuredContent"]["message"])

    def test_team_fee_returns_a_pay_link(self) -> None:
        self.tournament.teams.remove(self.team)
        args = {**self.args, "what": "team_fee"}

        with self.order(TEAM_FEE):
            result = self.confirmed("pay_for_team", args)

        data = result["structuredContent"]
        self.assertEqual(TEAM_FEE, data["amount_paise"])
        transaction = RazorpayTransaction.objects.get(order_id=data["order_id"])
        self.assertEqual(TEAM_FEE, transaction.amount)
        self.assertIn("₹5,000", self.asked("pay_for_team", args))

    def test_partial_team_fee_orders_the_partial_amount(self) -> None:
        self.tournament.teams.remove(self.team)

        with self.order(self.event.partial_team_fee):
            result = self.confirmed("pay_for_team", {**self.args, "what": "team_fee_partial"})

        self.assertEqual(self.event.partial_team_fee, result["structuredContent"]["amount_paise"])

    def test_a_second_partial_team_fee_is_refused(self) -> None:
        self.tournament.teams.remove(self.team)
        self.tournament.partial_teams.add(self.team)

        result = self.call("pay_for_team", {**self.args, "what": "team_fee_partial"})

        self.assertTrue(result["isError"])
        self.assertIn("already paid", result["structuredContent"]["message"])
        self.assertFalse(RazorpayTransaction.objects.exists())

    def test_a_team_fee_that_moved_is_refused_with_the_new_price_and_no_order(self) -> None:
        self.tournament.teams.remove(self.team)
        stale = {"team_fee": TEAM_FEE - 100, "team_fee_partial": 0}

        with (
            mock.patch.object(team_registration, "_fee", return_value=stale),
            self.order(TEAM_FEE) as create,
        ):
            result = self.confirmed("pay_for_team", {**self.args, "what": "team_fee"})

        self.assertTrue(result["isError"])
        self.assertIn("The team fee is now ₹5,000", result["structuredContent"]["message"])
        create.assert_not_called()
        self.assertFalse(RazorpayTransaction.objects.exists())

    def test_a_paid_team_fee_is_not_asked_for_again(self) -> None:
        result = self.call("pay_for_team", {**self.args, "what": "team_fee"})

        self.assertTrue(result["isError"])
        self.assertIn("already paid", result["structuredContent"]["message"])

    def test_a_non_admin_is_denied(self) -> None:
        other = User.objects.create_user("o@x.com", "o@x.com", "pw")
        Team.objects.create(name="Elsewhere").admins.add(other)
        make_token(other, "otok", scope="hub:read hub:write")

        result = self.call("pay_for_team", {**self.args, "what": "roster"}, "otok")

        self.assertTrue(result["isError"])
        self.assertTrue(result["structuredContent"]["message"].startswith("Not allowed"))


class TestRegisterTeam(Case):
    def test_registers_a_team_for_a_free_event(self) -> None:
        free = Event.objects.create(
            title="Free Open",
            start_date=today() + datetime.timedelta(days=30),
            end_date=today() + datetime.timedelta(days=31),
            team_registration_start_date=today() - datetime.timedelta(days=1),
            team_registration_end_date=today() + datetime.timedelta(days=10),
            player_registration_start_date=today() - datetime.timedelta(days=1),
            player_registration_end_date=today() + datetime.timedelta(days=10),
        )
        tournament = Tournament.objects.create(event=free)

        result = self.confirmed(
            "register_team", {"team_slug": self.team.slug, "event_slug": free.slug}
        )

        self.assertTrue(result["structuredContent"]["done"], result)
        self.assertTrue(tournament.teams.filter(pk=self.team.pk).exists())

    def test_a_paid_event_points_to_pay_for_team(self) -> None:
        result = self.call(
            "register_team", {"team_slug": self.team.slug, "event_slug": self.event.slug}
        )

        self.assertTrue(result["isError"])
        self.assertEqual(
            "Use pay_for_team with what=team_fee.", result["structuredContent"]["hint"]
        )

    def test_registers_a_team_for_a_series(self) -> None:
        other = Team.objects.create(name="Newcomers", category=self.team.category)
        other.admins.add(self.admin)

        result = self.confirmed(
            "register_team", {"team_slug": other.slug, "series_slug": self.series.slug}
        )

        self.assertTrue(result["structuredContent"]["done"], result)
        self.assertTrue(self.series.teams.filter(pk=other.pk).exists())

    def test_one_of_series_or_event_is_needed(self) -> None:
        result = self.call("register_team", {"team_slug": self.team.slug})

        self.assertTrue(result["isError"])

    def test_a_team_the_user_does_not_admin_is_refused(self) -> None:
        other = Team.objects.create(name="Not Mine")

        result = self.call(
            "register_team", {"team_slug": other.slug, "series_slug": self.series.slug}
        )

        self.assertTrue(result["isError"])
        self.assertTrue(result["structuredContent"]["message"].startswith("Not allowed"))


class TestNextAction(SimpleTestCase):
    def test_a_roster_action_names_the_player(self) -> None:
        row = team_registration._next(
            "waiting.invite", "resend_invite", "Resend", {"event_slug": "e", "team_slug": "t"}, 7
        )

        self.assertEqual("resend_roster_invites", row["tool"])
        self.assertEqual({"event_slug": "e", "team_slug": "t", "player_ids": [7]}, row["arguments"])
