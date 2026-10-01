"""The team registration home's API."""

import datetime
from typing import Any
from unittest import mock

from django.core import mail
from django.test import Client, override_settings
from django.utils.timezone import now
from razorpay.resources.order import Order
from razorpay.resources.payment import Payment

from server.core.models import Player, Team, User
from server.registration.models import RosterEntry, RosterSwap
from server.registration.state import build_context
from server.series.models import Role, SeriesRegistration, SeriesRosterInvitation
from server.subscription.models import Subscription
from server.tests.base import make_account
from server.tests.test_payment_accounts import PLAYER_FEE, razorpay_order
from server.tests.test_registration_state import StateTestCase
from server.tournament.models import Event, Registration
from server.transaction.models import RazorpayTransaction, RazorpayTransactionPlayer
from server.transaction.utils import apply_transaction
from server.utils import today


# Invites are emailed with a signed link.
@override_settings(EMAIL_SECRET_KEY="test-invite-key")  # noqa: S106
class ApiCase(StateTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.web = Client()
        self.web.force_login(self.admin)
        self.base = f"/api/registration/{self.event.slug}/team/{self.team.slug}"

    def status(self, client: Client | None = None) -> Any:
        return (client or self.web).get(self.base)

    def as_user(self, user: User) -> Client:
        client = Client()
        client.force_login(user)
        return client

    def step(self, key: str) -> dict[str, Any]:
        return next(s for s in self.status().json()["steps"] if s["key"] == key)

    def held(self, player: Player, *, by: User | None = None, minutes_ago: int = 0) -> Any:
        """An earlier checkout's order holding this player."""
        by = by or User.objects.create_user("o@x.com", "o@x.com", "pw")
        order = RazorpayTransaction.objects.create(
            order_id=f"order_{player.id}",
            amount=self.event.player_fee,
            currency="INR",
            status="created",
            user=by,
            event=self.event,
            team=self.team,
            type="player-reg",
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=order, player=player, amount=self.event.player_fee
        )
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            payment_date=now() - datetime.timedelta(minutes=minutes_ago)
        )
        RosterEntry.objects.filter(player=player).update(held_by_order=order)
        return order


class TestStatus(ApiCase):
    def test_rows_waiting_for_the_team_fee_are_not_waiting_on_the_player(self) -> None:
        self.tournament.teams.remove(self.team)
        self.player("a@x.com")
        self.assertIsNone(self.step("roster")["callout"])

    def test_shape(self) -> None:
        self.player("a@x.com")
        body = self.status().json()
        self.assertEqual("admin", body["viewer"])
        self.assertEqual(
            ["series", "team_fee", "roster", "game_day"], [s["key"] for s in body["steps"]]
        )
        self.assertEqual("ready", body["roster"]["entries"][0]["state"]["code"])
        self.assertEqual(1, len(body["checkout"]["ready_ids"]))
        self.assertEqual(self.event.player_fee, body["checkout"]["amount"])
        self.assertNotIn("pending_order", body)
        event = body["event"]
        self.assertEqual(
            self.event.player_registration_end_date.isoformat(),
            event["player_registration_end_date"],
        )
        for name in (
            "team_registration_start_date",
            "team_registration_end_date",
            "team_late_penalty_end_date",
            "player_registration_start_date",
            "player_late_penalty_end_date",
        ):
            value = getattr(self.event, name)
            self.assertEqual(value.isoformat() if value else None, event[name])
        self.assertEqual(self.event.team_late_penalty, event["team_late_penalty"])
        self.assertEqual(self.event.player_late_penalty, event["player_late_penalty"])

    def test_outsider_gets_404_and_member_is_read_only(self) -> None:
        outsider = self.as_user(User.objects.create_user("o@x.com", "o@x.com", "pw"))
        self.assertEqual(404, self.status(outsider).status_code)
        member = self.player("m@x.com", entry=False, on_series=False)
        Registration.objects.create(event=self.event, team=self.team, player=member)
        as_member = self.as_user(member.user)
        self.assertEqual("member", self.status(as_member).json()["viewer"])
        response = as_member.post(
            f"{self.base}/roster", {"player_id": member.id}, content_type="application/json"
        )
        self.assertEqual(403, response.status_code)

    def test_series_roster_member_and_staff_can_read(self) -> None:
        member = self.player("m@x.com", entry=False)
        self.assertEqual("member", self.status(self.as_user(member.user)).json()["viewer"])
        staff = User.objects.create_user("s@x.com", "s@x.com", "pw", is_staff=True)
        self.assertEqual("staff", self.status(self.as_user(staff)).json()["viewer"])

    def test_unknown_team_is_404(self) -> None:
        response = self.web.get(f"/api/registration/{self.event.slug}/team/nope")
        self.assertEqual(404, response.status_code)

    def test_non_series_event_has_no_series_step(self) -> None:
        self.event.series = None
        self.event.save()
        self.assertNotIn("series", [s["key"] for s in self.status().json()["steps"]])

    def test_team_fee_step_before_opening(self) -> None:
        self.tournament.teams.remove(self.team)
        Event.objects.filter(pk=self.event.pk).update(
            team_registration_start_date=today() + datetime.timedelta(days=3)
        )
        step = self.step("team_fee")
        self.assertEqual(("locked", "timing"), (step["state"], step["callout"]["kind"]))
        self.assertIn("in 3 days", step["callout"]["text"])
        self.assertEqual("locked", self.step("roster")["state"])

    def test_team_fee_step_open_and_paid(self) -> None:
        self.assertEqual("done", self.step("team_fee")["state"])
        self.tournament.teams.remove(self.team)
        step = self.step("team_fee")
        self.assertEqual(("current", "pay_team"), (step["state"], step["callout"]["action"]["op"]))

    def test_series_step_when_the_team_is_not_in_the_series(self) -> None:
        self.series.teams.remove(self.team)
        step = self.step("series")
        self.assertEqual(
            ("current", "register_series"), (step["state"], step["callout"]["action"]["op"])
        )

    def test_subscriptions_needed_builds_the_handoff_link(self) -> None:
        p = self.player("a@x.com", tier=None)
        roster = self.step("roster")
        self.assertEqual("action", roster["callout"]["kind"])
        href = roster["callout"]["action"]["href"]
        self.assertIn(f"players={p.id}", href)
        self.assertIn(
            f"return=/tournament/{self.event.slug}/team/{self.team.slug}/registration", href
        )

    def test_upgrade_link_returns_to_this_page(self) -> None:
        self.player("a@x.com", tier="community")
        href = self.status().json()["roster"]["entries"][0]["state"]["action"]["href"]
        self.assertIn(f"return=/tournament/{self.event.slug}/team/{self.team.slug}/", href)
        self.assertNotIn("__RETURN__", href)

    def test_game_day_is_done_when_everyone_is_paid(self) -> None:
        p = self.player("a@x.com", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=p)
        self.assertEqual("done", self.step("roster")["state"])
        self.assertEqual("done", self.step("game_day")["state"])

    def test_team_fee_offers_the_partial_fee_while_its_window_is_open(self) -> None:
        self.tournament.teams.remove(self.team)
        callout = self.step("team_fee")["callout"]
        self.assertEqual("pay_team", callout["action"]["op"])
        self.assertEqual(
            {"label": "Pay partial ₹2,000", "op": "pay_team_partial", "href": None},
            callout["secondary_action"],
        )
        Event.objects.filter(pk=self.event.pk).update(
            team_partial_registration_end_date=today() - datetime.timedelta(days=1)
        )
        self.assertNotIn("secondary_action", self.step("team_fee")["callout"])

    def team_order(self, status: str) -> RazorpayTransaction:
        return RazorpayTransaction.objects.create(
            order_id=f"order_{status}",
            amount=self.event.team_fee,
            currency="INR",
            status=status,
            user=self.admin,
            event=self.event,
            team=self.team,
            type="team-reg",
        )

    def test_a_withdrawn_team_is_told_it_was_refunded(self) -> None:
        self.tournament.teams.remove(self.team)
        self.team_order("refunded")
        step = self.step("team_fee")
        # Still open, so it can pay again.
        self.assertEqual("Withdrawn · refunded ₹5,000", step["detail"])
        self.assertEqual("pay_team", step["callout"]["action"]["op"])
        Event.objects.filter(pk=self.event.pk).update(
            team_registration_end_date=today() - datetime.timedelta(days=1)
        )
        step = self.step("team_fee")
        self.assertEqual("locked", step["state"])
        self.assertEqual(
            {"kind": "timing", "text": "Withdrawn · refunded ₹5,000", "action": None},
            step["callout"],
        )

    def test_a_failed_team_fee_order_changes_nothing(self) -> None:
        self.tournament.teams.remove(self.team)
        self.team_order("failed")
        step = self.step("team_fee")
        self.assertEqual(
            ("current", "pay_team", ""),
            (step["state"], step["callout"]["action"]["op"], step["detail"]),
        )

    def test_series_step_once_series_registration_closed(self) -> None:
        self.series.teams.remove(self.team)
        self.series.end_date = today() - datetime.timedelta(days=1)
        self.series.save()
        step = self.step("series")
        self.assertEqual(("locked", "timing"), (step["state"], step["callout"]["kind"]))
        self.assertEqual(
            f"Series registration closed on {self.series.end_date:%b %-d}", step["callout"]["text"]
        )
        self.assertEqual("Ask organisers", step["callout"]["action"]["label"])

    def test_free_player_fee_accepted_invite_is_added_not_paid(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(player_fee=0)
        p = self.player("a@x.com")  # on the series roster: the invite was accepted
        body = self.status().json()
        state = body["roster"]["entries"][0]["state"]
        self.assertEqual(
            ("ready.free", "ready", "roster"), (state["code"], state["kind"], state["action"]["op"])
        )
        self.assertEqual([], body["checkout"]["ready_ids"])
        # It can be rostered now, so it counts toward the meter like a ready row.
        self.assertEqual(1, body["roster"]["meter"]["total"])
        response = self.web.post(
            f"{self.base}/roster", {"player_id": p.id}, content_type="application/json"
        )
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("done.rostered", response.json()["state"]["code"])
        self.assertTrue(Registration.objects.filter(team=self.team, player=p).exists())
        self.assertFalse(RosterEntry.objects.filter(player=p).exists())

    def part_paid(self) -> None:
        self.tournament.teams.remove(self.team)
        self.tournament.partial_teams.add(self.team)

    def test_part_paid_before_the_deadline_pays_the_rest(self) -> None:
        self.part_paid()
        step = self.step("team_fee")
        end = self.event.team_registration_end_date
        self.assertEqual(f"Partial paid · ₹3,000 remaining by {end:%b %-d}", step["detail"])
        self.assertEqual("Pay the remaining ₹3,000", step["callout"]["text"])
        self.assertEqual(
            {"label": "Pay ₹3,000", "op": "pay_team_rest", "href": None},
            step["callout"]["action"],
        )

    def test_part_paid_after_the_deadline_pays_the_rest_and_the_late_fee(self) -> None:
        # create_transaction adds the late fee to the rest, not to a partial.
        self.part_paid()
        Event.objects.filter(pk=self.event.pk).update(
            team_registration_end_date=today() - datetime.timedelta(days=2),
            team_late_penalty_end_date=today() + datetime.timedelta(days=3),
            team_late_penalty=10000,
        )
        step = self.step("team_fee")
        self.assertEqual("Partial paid · ₹3,000 + 2 days × ₹100", step["detail"])  # noqa: RUF001
        self.assertEqual("Pay the remaining ₹3,200", step["callout"]["text"])
        self.assertEqual("Pay ₹3,200", step["callout"]["action"]["label"])

    def test_no_team_fee_is_taken_until_payments_are_set_up(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(payment_account=make_account(is_active=False))
        blocked = {
            "kind": "blocked",
            "text": "Payments for this tournament aren't set up yet — contact organisers",
            "action": None,
        }
        self.tournament.teams.remove(self.team)
        self.assertEqual(blocked, self.step("team_fee")["callout"])
        self.part_paid()
        self.assertEqual(blocked, self.step("team_fee")["callout"])

    def test_the_handoff_leaves_out_players_no_plan_can_be_bought_for(self) -> None:
        self.season.plans.filter(type__requires_grant=False).update(is_available=False)
        stuck = self.player("a@x.com", tier=None)
        granted = self.player("b@x.com", tier=None)
        granted.sponsorships.create(season=self.season)
        body = self.status().json()
        codes = {e["player"]["id"]: e["state"]["code"] for e in body["roster"]["entries"]}
        self.assertEqual({stuck.id: "waiting.approval", granted.id: "action.subscription"}, codes)
        callout = next(s for s in body["steps"] if s["key"] == "roster")["callout"]
        self.assertTrue(callout["text"].startswith("1 player needs"), callout["text"])
        self.assertIn(f"players={granted.id}&", callout["action"]["href"])
        self.assertNotIn(f"{stuck.id}:", callout["action"]["href"])


class TestRosterWrites(ApiCase):
    def add(self, player_id: int) -> Any:
        return self.web.post(
            f"{self.base}/roster", {"player_id": player_id}, content_type="application/json"
        )

    def test_adding_a_series_rostered_player_creates_an_entry(self) -> None:
        p = self.player("a@x.com", entry=False)
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("ready", response.json()["state"]["code"])
        self.assertEqual(self.admin, RosterEntry.objects.get(player=p).added_by)

    def test_adding_someone_off_the_series_roster_invites_them(self) -> None:
        p = self.player("a@x.com", on_series=False, entry=False)
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("waiting.invite", response.json()["state"]["code"])
        self.assertTrue(SeriesRosterInvitation.objects.filter(to_player=p, team=self.team).exists())

    def test_adding_someone_already_invited_keeps_the_invite(self) -> None:
        p = self.player("a@x.com", on_series=False, entry=False)
        SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.admin, to_player=p, team=self.team
        )
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(1, SeriesRosterInvitation.objects.filter(to_player=p).count())

    def test_inviting_again_after_an_invite_expired(self) -> None:
        p = self.player("a@x.com", on_series=False)
        old = SeriesRosterInvitation.objects.create(
            series=self.series,
            from_user=self.admin,
            to_player=p,
            team=self.team,
            expires_on=today() - datetime.timedelta(days=1),
        )
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        old.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.REVOKED, old.status)
        fresh = SeriesRosterInvitation.objects.exclude(pk=old.pk).get(to_player=p)
        self.assertEqual(SeriesRosterInvitation.Status.PENDING, fresh.status)
        self.assertEqual("waiting.invite", response.json()["state"]["code"])

    def test_on_another_teams_series_roster_is_refused(self) -> None:
        p = self.player("a@x.com", on_series=False, entry=False)
        rival = Team.objects.create(name="Rivals")
        self.series.teams.add(rival)
        SeriesRegistration.objects.create(
            series=self.series, team=rival, player=p, role=Role.DEFAULT
        )
        self.assertEqual(400, self.add(p.id).status_code)
        self.assertFalse(RosterEntry.objects.filter(player=p).exists())

    def test_unknown_player(self) -> None:
        self.assertEqual(400, self.add(99999).status_code)

    def test_free_player_fee_rosters_directly(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(player_fee=0)
        p = self.player("a@x.com", entry=False)
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("done.rostered", response.json()["state"]["code"])
        self.assertTrue(Registration.objects.filter(player=p, team=self.team).exists())
        self.assertFalse(RosterEntry.objects.exists())

    def test_free_player_fee_is_refused_once_rostering_closed(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(
            player_fee=0, player_registration_end_date=today() - datetime.timedelta(days=1)
        )
        p = self.player("a@x.com", entry=False)
        self.assertEqual(400, self.add(p.id).status_code)
        self.assertFalse(Registration.objects.filter(player=p).exists())

    def test_free_player_fee_rosters_through_the_late_window(self) -> None:
        # The row reads "Add to roster" until the late window ends, so it adds.
        Event.objects.filter(pk=self.event.pk).update(
            player_fee=0,
            player_registration_end_date=today() - datetime.timedelta(days=1),
            player_late_penalty_end_date=today() + datetime.timedelta(days=2),
        )
        p = self.player("a@x.com", entry=False)
        response = self.add(p.id)
        self.assertEqual(201, response.status_code, response.content)
        self.assertTrue(Registration.objects.filter(player=p, team=self.team).exists())

    def test_remove_a_draft_but_not_a_paid_player(self) -> None:
        draft = self.player("a@x.com")
        self.assertEqual(204, self.web.delete(f"{self.base}/roster/{draft.id}").status_code)
        self.assertFalse(RosterEntry.objects.exists())
        paid = self.player("p@x.com", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=paid)
        self.assertEqual(409, self.web.delete(f"{self.base}/roster/{paid.id}").status_code)
        self.assertEqual(404, self.web.delete(f"{self.base}/roster/99999").status_code)

    def test_undo_on_a_free_tournament_takes_them_off_the_roster(self) -> None:
        # Nothing was paid, so the Add dialog's Undo works after rostering.
        Event.objects.filter(pk=self.event.pk).update(player_fee=0)
        p = self.player("a@x.com", entry=False)
        self.assertEqual(201, self.add(p.id).status_code)
        self.assertEqual(204, self.web.delete(f"{self.base}/roster/{p.id}").status_code)
        self.assertFalse(Registration.objects.filter(player=p).exists())
        self.assertFalse(RosterEntry.objects.filter(player=p).exists())

    def test_free_tournament_roster_is_kept_once_rostering_closed(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(
            player_fee=0, player_registration_end_date=today() - datetime.timedelta(days=1)
        )
        p = self.player("a@x.com", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=p)
        self.assertEqual(409, self.web.delete(f"{self.base}/roster/{p.id}").status_code)
        self.assertTrue(Registration.objects.filter(player=p).exists())

    def test_resend_invite(self) -> None:
        p = self.player("a@x.com", on_series=False)
        SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.admin, to_player=p, team=self.team
        )
        response = self.web.post(f"{self.base}/roster/{p.id}/resend-invite")
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual(2, SeriesRosterInvitation.objects.filter(to_player=p).count())
        self.assertEqual(
            1,
            SeriesRosterInvitation.objects.filter(
                to_player=p, status=SeriesRosterInvitation.Status.PENDING
            ).count(),
        )

    def test_writes_are_for_admins(self) -> None:
        p: Player = self.player("a@x.com")
        member = self.as_user(p.user)
        self.assertEqual(403, member.delete(f"{self.base}/roster/{p.id}").status_code)
        self.assertEqual(403, member.post(f"{self.base}/roster/{p.id}/resend-invite").status_code)


class TestCheckout(ApiCase):
    def pay(
        self,
        expected: int,
        razorpay_status: str | Exception = "created",
        ids: list[int] | None = None,
    ) -> Any:
        """Check out, with Razorpay answered locally.

        `ids` are who the page showed as ready, by default what it shows now.
        `razorpay_status` is what Razorpay says about an earlier order that
        held these players.
        """
        if ids is None:
            ids = self.status().json()["checkout"]["ready_ids"]
        fetched: dict[str, Any] = (
            {"side_effect": razorpay_status}
            if isinstance(razorpay_status, Exception)
            else {"return_value": {"status": razorpay_status}}
        )
        captured = {"items": [{"id": "pay_earlier", "status": "captured"}]}
        with (
            mock.patch.object(
                Order, "create", autospec=True, return_value=razorpay_order(expected)
            ) as self.create,
            mock.patch.object(Order, "fetch", autospec=True, **fetched) as self.fetch,
            mock.patch.object(Order, "payments", autospec=True, return_value=captured),
        ):
            return self.web.post(
                f"{self.base}/checkout",
                {"expected_amount": expected, "expected_ids": ids},
                content_type="application/json",
            )

    def test_pays_only_ready_players_in_one_order(self) -> None:
        a, b = self.player("a@x.com"), self.player("b@x.com")
        self.player("w@x.com", waiver=False)
        response = self.pay(2 * self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        order = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual({a.id, b.id}, set(order.players.values_list("id", flat=True)))
        self.assertEqual(2, RosterEntry.objects.filter(held_by_order=order).count())

    def test_the_checkout_window_closes_when_the_hold_does(self) -> None:
        self.player("a@x.com")
        response = self.pay(self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(20 * 60, response.json()["timeout"])  # Razorpay's, in seconds

    def test_checkout_refuses_a_changed_amount(self) -> None:
        self.player("a@x.com")
        response = self.pay(1)
        self.assertEqual(409, response.status_code)
        self.assertEqual(
            {"removed": [], "old_amount": 1, "new_amount": self.event.player_fee},
            response.json(),
        )
        self.assertFalse(RazorpayTransaction.objects.exists())

    def test_nothing_ready(self) -> None:
        self.player("w@x.com", waiver=False)
        self.assertEqual(400, self.pay(0).status_code)

    def test_nothing_to_pay_without_a_player_fee(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(player_fee=0)
        self.player("a@x.com")
        response = self.pay(0, ids=[])
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Nothing to pay — this tournament has no player fee", response.json()["message"]
        )
        self.create.assert_not_called()

    def test_checkout_refuses_a_changed_set_of_players(self) -> None:
        a = self.player("a@x.com")
        b = self.player("b@x.com", waiver=False)
        at_load = self.status().json()["checkout"]["ready_ids"]
        self.assertEqual([a.id], at_load)
        # Same total, different people: A's waiver lapsed, B signed theirs.
        Subscription.objects.filter(player=a).update(waiver_valid=False)
        Subscription.objects.filter(player=b).update(waiver_valid=True)
        response = self.pay(self.event.player_fee, ids=at_load)
        self.assertEqual(409, response.status_code, response.content)
        self.assertEqual(
            [{"player_id": a.id, "reason": "Waiver not signed — only the player can sign it"}],
            response.json()["removed"],
        )
        self.create.assert_not_called()

    def test_the_ready_set_is_counted_again_under_the_lock(self) -> None:
        a, b = self.player("a@x.com"), self.player("b@x.com")
        at_load = self.status().json()["checkout"]["ready_ids"]
        other = User.objects.create_user("o2@x.com", "o2@x.com", "pw")
        real = build_context

        def then_another_admin_checks_out(*args: Any, **kwargs: Any) -> Any:
            ctx = real(*args, **kwargs)
            if not RosterEntry.objects.filter(held_by_order__isnull=False).exists():
                self.held(b, by=other)  # between the first read and the locked one
            return ctx

        with mock.patch(
            "server.registration.api.build_context", side_effect=then_another_admin_checks_out
        ):
            response = self.pay(2 * self.event.player_fee, ids=at_load)
        self.assertEqual(409, response.status_code, response.content)
        self.assertEqual(
            [{"player_id": b.id, "reason": "Being paid by another admin"}],
            response.json()["removed"],
        )
        self.assertEqual(self.event.player_fee, response.json()["new_amount"])
        self.create.assert_not_called()
        self.assertEqual(
            {a.id},
            set(RosterEntry.objects.filter(held_by_order=None).values_list("player_id", flat=True)),
        )

    def test_admins_only(self) -> None:
        p = self.player("a@x.com")
        self.web.force_login(p.user)
        self.assertEqual(403, self.pay(self.event.player_fee).status_code)

    def test_skips_players_another_admin_is_paying_for(self) -> None:
        a, b = self.player("a@x.com"), self.player("b@x.com")
        self.held(b)
        response = self.pay(self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        order = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual([a.id], list(order.players.values_list("id", flat=True)))
        self.fetch.assert_not_called()

    def test_a_hold_older_than_twenty_minutes_is_released(self) -> None:
        p = self.player("a@x.com")
        stale = self.held(p, minutes_ago=21)
        response = self.pay(self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        self.fetch.assert_called_once()
        self.assertEqual(stale.order_id, self.fetch.call_args.args[1])
        order = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual([p.id], list(order.players.values_list("id", flat=True)))
        self.assertEqual(order, RosterEntry.objects.get(player=p).held_by_order)

    def test_a_hold_is_released_when_razorpay_cant_be_asked(self) -> None:
        p = self.player("a@x.com")
        self.held(p, minutes_ago=21)
        response = self.pay(self.event.player_fee, razorpay_status=ConnectionError("down"))
        self.assertEqual(200, response.status_code, response.content)
        order = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual([p.id], list(order.players.values_list("id", flat=True)))

    def test_a_stale_hold_razorpay_took_money_for_is_settled_not_charged_again(self) -> None:
        p = self.player("a@x.com")
        stale = self.held(p, minutes_ago=21)
        response = self.pay(self.event.player_fee, razorpay_status="paid")
        # Nobody left to pay for: they're rostered now.
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn("went through", response.json()["message"])
        self.create.assert_not_called()
        stale.refresh_from_db()
        self.assertEqual(("completed", "pay_earlier"), (stale.status, stale.payment_id))
        self.assertTrue(Registration.objects.filter(team=self.team, player=p).exists())
        self.assertFalse(RosterEntry.objects.filter(player=p).exists())

    def test_settling_an_earlier_payment_changes_the_total(self) -> None:
        paid, fresh = self.player("a@x.com"), self.player("b@x.com")
        self.held(paid, minutes_ago=21)
        response = self.pay(2 * self.event.player_fee, razorpay_status="paid")
        self.assertEqual(409, response.status_code, response.content)
        self.fetch.assert_called_once()
        body = response.json()
        self.assertEqual([paid.id], [r["player_id"] for r in body["removed"]])
        self.assertEqual(self.event.player_fee, body["new_amount"])
        response = self.pay(self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        order = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual([fresh.id], list(order.players.values_list("id", flat=True)))

    def test_my_own_open_checkout_razorpay_took_money_for_is_not_charged_again(self) -> None:
        p = self.player("a@x.com")
        self.held(p, by=self.admin)
        self.assertEqual(400, self.pay(self.event.player_fee, razorpay_status="paid").status_code)
        self.create.assert_not_called()
        self.assertTrue(Registration.objects.filter(team=self.team, player=p).exists())

    def test_routed_to_the_state_account(self) -> None:
        account = make_account()
        Event.objects.filter(pk=self.event.pk).update(payment_account=account)
        self.player("a@x.com")
        response = self.pay(self.event.player_fee)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(account.key_id, self.create.call_args.args[0].client.auth[0])
        self.assertEqual(account.key_id, response.json()["key"])


class TestCandidates(ApiCase):
    def get(self, text: str = "", page: int = 1) -> Any:
        return self.web.get(f"{self.base}/candidates", {"text": text, "page": str(page)})

    def past_event(self, title: str, days_ago: int) -> Event:
        return Event.objects.create(
            title=title,
            start_date=today() - datetime.timedelta(days=days_ago + 2),
            end_date=today() - datetime.timedelta(days=days_ago),
            team_registration_start_date=today() - datetime.timedelta(days=days_ago + 30),
            team_registration_end_date=today() - datetime.timedelta(days=days_ago + 10),
            player_registration_start_date=today() - datetime.timedelta(days=days_ago + 30),
            player_registration_end_date=today() - datetime.timedelta(days=days_ago + 10),
        )

    def test_admins_only(self) -> None:
        outsider = User.objects.create_user("o@x.com", "o@x.com", "pw")
        self.assertEqual(403, self.as_user(outsider).get(f"{self.base}/candidates").status_code)

    def test_browse_lists_series_then_past_teammates_newest_first(self) -> None:
        on_series = self.player("s@x.com", entry=False)
        older = self.player("old@x.com", on_series=False, entry=False)
        newer = self.player("new@x.com", on_series=False, entry=False)
        Registration.objects.create(
            event=self.past_event("Old Cup", 300), team=self.team, player=older
        )
        Registration.objects.create(
            event=self.past_event("New Cup", 30), team=self.team, player=newer
        )
        Registration.objects.create(
            event=self.past_event("Mid Cup", 100), team=self.team, player=newer
        )
        body = self.get().json()
        self.assertEqual(["series", "past"], [g["key"] for g in body["groups"]])
        self.assertEqual([on_series.id], [p["id"] for p in body["groups"][0]["players"]])
        past = body["groups"][1]["players"]
        self.assertEqual([newer.id, older.id], [p["id"] for p in past])
        self.assertEqual("New Cup", past[0]["last_event"])
        self.assertEqual(2, past[0]["events"])
        self.assertEqual("Played for Home before", body["groups"][1]["title"])

    def test_browse_leaves_out_people_already_on_the_list(self) -> None:
        listed = self.player("l@x.com")
        body = self.get().json()
        ids = [p["id"] for g in body["groups"] for p in g["players"]]
        self.assertNotIn(listed.id, ids)

    def test_search_puts_teammates_first(self) -> None:
        stranger = self.player("zed.alpha@x.com", on_series=False, entry=False)
        mate = self.player("zed.beta@x.com", entry=False)
        body = self.get("zed").json()
        self.assertEqual(["matches", "others"], [g["key"] for g in body["groups"]])
        self.assertEqual([mate.id], [p["id"] for p in body["groups"][0]["players"]])
        self.assertEqual([stranger.id], [p["id"] for p in body["groups"][1]["players"]])

    def test_search_marks_people_on_the_list(self) -> None:
        listed = self.player("zed@x.com")
        players = [p for g in self.get("zed").json()["groups"] for p in g["players"]]
        self.assertEqual([True], [p["on_list"] for p in players if p["id"] == listed.id])

    def test_hints_and_buttons(self) -> None:
        invitee = self.player("i@x.com", on_series=False, entry=False)
        no_sub = self.player("n@x.com", tier=None, entry=False)
        rows = {p["id"]: p for g in self.get().json()["groups"] for p in g["players"]}
        rows |= {p["id"]: p for g in self.get("i@x").json()["groups"] for p in g["players"]}
        self.assertEqual("invite", rows[invitee.id]["button"])
        self.assertEqual(
            "Not on the series roster — they'll get an invite", rows[invitee.id]["hint"]["text"]
        )
        self.assertEqual("Needs a subscription after adding", rows[no_sub.id]["hint"]["text"])

    def test_me_when_not_on_the_list(self) -> None:
        me = self.player("admin-player@x.com", entry=False)
        me.user = self.admin
        me.save()
        body = self.get().json()
        self.assertEqual(me.id, body["me"]["id"])
        ids = [p["id"] for g in body["groups"] for p in g["players"]]
        self.assertNotIn(me.id, ids)

    def test_me_off_the_series_roster_will_join_it(self) -> None:
        me = self.player("admin-player@x.com", on_series=False, entry=False)
        me.user = self.admin
        me.save()
        mine = self.get().json()["me"]
        self.assertEqual(("ready.self", "add"), (mine["hint"]["code"], mine["button"]))

    def test_me_who_cannot_join_the_series_roster_is_told_why(self) -> None:
        me = self.player("admin-player@x.com", on_series=False, entry=False, tier=None)
        me.user = self.admin
        me.save()
        mine = self.get().json()["me"]
        self.assertEqual("blocked.self_subscription", mine["hint"]["code"])
        self.assertIsNone(mine["button"])

    def test_no_me_without_a_profile(self) -> None:
        self.assertIsNone(self.get().json()["me"])

    def test_search_pages(self) -> None:
        for i in range(12):
            self.player(f"many{i:02}@x.com", on_series=False, entry=False)
        first = self.get("many").json()
        self.assertTrue(first["has_more"])
        self.assertEqual(10, sum(len(g["players"]) for g in first["groups"]))
        second = self.get("many", page=2).json()
        self.assertFalse(second["has_more"])
        self.assertEqual(2, sum(len(g["players"]) for g in second["groups"]))


class TestAddMyselfAndRemove(ApiCase):
    def own_player(self) -> Player:
        p = self.player("me@x.com", on_series=False, entry=False)
        p.user = self.admin
        p.save()
        return p

    def test_adding_myself_joins_the_series_roster_without_an_invite(self) -> None:
        me = self.own_player()
        r = self.web.post(
            f"{self.base}/roster", {"player_id": me.id}, content_type="application/json"
        )
        self.assertEqual(201, r.status_code, r.content)
        self.assertTrue(
            SeriesRegistration.objects.filter(
                series=self.series, team=self.team, player=me
            ).exists()
        )
        self.assertFalse(SeriesRosterInvitation.objects.filter(to_player=me).exists())
        self.assertEqual(0, len(mail.outbox))

    def test_adding_myself_respects_the_series_roster_cap(self) -> None:
        self.series.series_roster_max_players = 0
        self.series.save()
        me = self.own_player()
        r = self.web.post(
            f"{self.base}/roster", {"player_id": me.id}, content_type="application/json"
        )
        self.assertEqual(400, r.status_code)
        self.assertFalse(RosterEntry.objects.filter(player=me).exists())

    def test_removing_withdraws_a_pending_invite(self) -> None:
        p = self.player("i@x.com", on_series=False, entry=False)
        self.web.post(f"{self.base}/roster", {"player_id": p.id}, content_type="application/json")
        invite = SeriesRosterInvitation.objects.get(to_player=p)
        self.assertEqual(204, self.web.delete(f"{self.base}/roster/{p.id}").status_code)
        invite.refresh_from_db()
        self.assertEqual(SeriesRosterInvitation.Status.REVOKED, invite.status)

    def test_removing_keeps_an_existing_series_place(self) -> None:
        p = self.player("s@x.com")
        self.assertEqual(204, self.web.delete(f"{self.base}/roster/{p.id}").status_code)
        self.assertTrue(SeriesRegistration.objects.filter(player=p).exists())


class TestSwap(ApiCase):
    def rostered(self, email: str, match_up: str = Player.MatchupTypes.FEMALE) -> Player:
        p = self.player(email, match_up, entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=p)
        return p

    def swap(self, out: Player, new: Player, client: Client | None = None) -> Any:
        return (client or self.web).post(
            f"{self.base}/swap",
            {"out_player_id": out.id, "in_player_id": new.id},
            content_type="application/json",
        )

    def paid_order(self, order_id: str, player: Player) -> RazorpayTransaction:
        order = RazorpayTransaction.objects.create(
            order_id=order_id,
            payment_id=f"pay_{order_id}",
            amount=PLAYER_FEE,
            currency="INR",
            status=RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            type=RazorpayTransaction.TransactionTypeChoices.PLAYER_REGISTRATION,
            user=self.admin,
            event=self.event,
            team=self.team,
        )
        RazorpayTransactionPlayer.objects.create(
            transaction=order, player=player, amount=PLAYER_FEE
        )
        return order

    def test_swap_moves_the_place(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        r = self.swap(out, new)
        self.assertEqual(200, r.status_code, r.content)
        self.assertTrue(
            Registration.objects.filter(event=self.event, team=self.team, player=new).exists()
        )
        self.assertFalse(Registration.objects.filter(event=self.event, player=out).exists())
        self.assertTrue(
            RosterEntry.objects.filter(event=self.event, team=self.team, player=out).exists()
        )
        self.assertFalse(RosterEntry.objects.filter(player=new).exists())
        swap = RosterSwap.objects.get()
        self.assertEqual((out, new, self.admin), (swap.out_player, swap.in_player, swap.by))

    def test_swapped_out_player_is_emailed(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        with self.captureOnCommitCallbacks(execute=True):
            self.swap(out, new)
        self.assertEqual(["o@x.com"], mail.outbox[-1].to)
        self.assertIn(f"taken off {self.team.name}'s roster", mail.outbox[-1].subject)

    def test_email_failure_keeps_the_swap(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        with (
            mock.patch("server.registration.api.mail.send_mail", side_effect=OSError("smtp")),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertEqual(200, self.swap(out, new).status_code)
        self.assertTrue(RosterSwap.objects.exists())

    def test_admins_only(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        outsider = User.objects.create_user("x@x.com", "x@x.com", "pw")
        self.assertEqual(403, self.swap(out, new, self.as_user(outsider)).status_code)

    def test_out_player_must_be_rostered(self) -> None:
        out, new = self.player("o@x.com"), self.player("n@x.com")
        r = self.swap(out, new)
        self.assertEqual(409, r.status_code)
        self.assertIn("no longer rostered", r.json()["message"])

    def test_in_player_must_be_on_the_list(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com", entry=False)
        self.assertEqual(409, self.swap(out, new).status_code)

    def test_in_player_must_be_ready(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com", tier=None)
        r = self.swap(out, new)
        self.assertEqual(409, r.status_code)
        self.assertFalse(RosterSwap.objects.exists())

    def test_second_swap_of_the_same_player_is_refused(self) -> None:
        out = self.rostered("o@x.com")
        a, b = self.player("a@x.com"), self.player("b@x.com")
        self.assertEqual(200, self.swap(out, a).status_code)
        self.assertEqual(409, self.swap(out, b).status_code)

    def test_swap_back(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.swap(out, new)
        self.assertEqual(200, self.swap(new, out).status_code)
        self.assertEqual(2, RosterSwap.objects.count())

    def test_admin_can_swap_themselves_out(self) -> None:
        me = self.rostered("me@x.com")
        me.user = self.admin
        me.save()
        self.assertEqual(200, self.swap(me, self.player("n@x.com")).status_code)

    def test_closed_window(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.event.player_registration_end_date = today() - datetime.timedelta(days=1)
        self.event.player_late_penalty_end_date = None
        self.event.save()
        r = self.swap(out, new)
        self.assertEqual(400, r.status_code)
        self.assertIn("Swaps closed", r.json()["message"])

    def test_uc_registration_tournaments_cannot_swap(self) -> None:
        self.tournament.use_uc_registrations = True
        self.tournament.save()
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.assertEqual(400, self.swap(out, new).status_code)

    def test_old_page_rosterings_can_be_swapped(self) -> None:
        # Rostered without ever being on the list, as the old pages did.
        out = self.rostered("o@x.com")
        self.assertFalse(RosterEntry.objects.filter(player=out).exists())
        self.assertEqual(200, self.swap(out, self.player("n@x.com")).status_code)

    def test_refused_rostering_rolls_back(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        with mock.patch(
            "server.registration.api.roster_player", return_value=(None, {"message": "nope"})
        ):
            self.assertEqual(409, self.swap(out, new).status_code)
        self.assertTrue(Registration.objects.filter(player=out).exists())
        self.assertTrue(RosterEntry.objects.filter(player=new).exists())

    def test_payload_says_who_was_swapped_and_when_paid(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.swap(out, new)
        rows = {r["player"]["id"]: r for r in self.status().json()["roster"]["entries"]}
        self.assertEqual(out.user.get_full_name(), rows[new.id]["swapped_for"]["name"])
        self.assertEqual(today().isoformat(), rows[new.id]["swapped_for"]["on"])
        self.assertIsNone(rows[out.id]["swapped_for"])
        self.assertIsNone(rows[new.id]["paid_on"])

    def test_paid_on_comes_from_the_completed_line(self) -> None:
        p = self.rostered("p@x.com")
        self.paid_order("order_paid1", p)
        rows = {r["player"]["id"]: r for r in self.status().json()["roster"]["entries"]}
        self.assertEqual(today().isoformat(), rows[p.id]["paid_on"])

    def test_dates_are_indian_dates(self) -> None:
        # 20:00 UTC is already the next day in India.
        late = datetime.datetime(2026, 9, 30, 20, 0, tzinfo=datetime.timezone.utc)
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.swap(out, new)
        RosterSwap.objects.update(at=late)
        RazorpayTransaction.objects.filter(pk=self.paid_order("order_late", new).pk).update(
            payment_date=late
        )
        row = next(
            r for r in self.status().json()["roster"]["entries"] if r["player"]["id"] == new.id
        )
        self.assertEqual(("2026-10-01", "2026-10-01"), (row["paid_on"], row["swapped_for"]["on"]))

    def test_paying_again_for_a_swapped_out_player_is_not_refunded(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        self.paid_order("order_first", out)
        self.assertEqual(200, self.swap(out, new).status_code)
        second = self.paid_order("order_second", out)
        with mock.patch.object(Payment, "refund", autospec=True) as refund:
            apply_transaction(second)
        refund.assert_not_called()
        self.assertTrue(
            Registration.objects.filter(event=self.event, team=self.team, player=out).exists()
        )

    def test_in_player_paid_for_by_a_lost_order_is_settled_not_swapped(self) -> None:
        # Razorpay took the money for a stale checkout; callback and webhook lost.
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        stale = self.held(new, by=self.admin, minutes_ago=21)
        captured = {"items": [{"id": "pay_earlier", "status": "captured"}]}
        with (
            mock.patch.object(Order, "fetch", autospec=True, return_value={"status": "paid"}),
            mock.patch.object(Order, "payments", autospec=True, return_value=captured),
            mock.patch.object(Payment, "refund", autospec=True) as refund,
        ):
            r = self.swap(out, new)
        self.assertEqual(409, r.status_code, r.content)
        self.assertEqual(
            "Their earlier payment went through; they're rostered now", r.json()["message"]
        )
        stale.refresh_from_db()
        self.assertEqual("completed", stale.status)
        refund.assert_not_called()
        self.assertFalse(RosterSwap.objects.exists())
        # Each keeps exactly the one place paid for.
        for p in (out, new):
            self.assertEqual(1, Registration.objects.filter(event=self.event, player=p).count())

    def test_swapped_in_player_keeps_their_series_role(self) -> None:
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        SeriesRegistration.objects.filter(player=new).update(role=Role.CAPTAIN)
        self.assertEqual(200, self.swap(out, new).status_code)
        self.assertEqual(Role.CAPTAIN, Registration.objects.get(player=new).role)

    def test_out_player_still_on_the_list_can_be_swapped(self) -> None:
        # Old pages and the admin roster without clearing the list entry.
        out, new = self.rostered("o@x.com"), self.player("n@x.com")
        RosterEntry.objects.create(event=self.event, team=self.team, player=out)
        r = self.swap(out, new)
        self.assertEqual(200, r.status_code, r.content)
        self.assertEqual(1, RosterEntry.objects.filter(player=out).count())

    def test_a_player_cannot_be_swapped_for_themselves(self) -> None:
        out = self.rostered("o@x.com")
        r = self.swap(out, out)
        self.assertEqual(400, r.status_code)
        self.assertEqual("Pick two different players", r.json()["message"])

    def test_swap_state_looks_past_a_full_roster(self) -> None:
        self.rostered("f1@x.com")
        self.rostered("m1@x.com", Player.MatchupTypes.MALE)
        self.rostered("m2@x.com", Player.MatchupTypes.MALE)  # total 3/3
        ready, unsubscribed = self.player("r@x.com"), self.player("u@x.com", tier=None)
        rows = {r["player"]["id"]: r for r in self.status().json()["roster"]["entries"]}
        self.assertEqual("limit.total", rows[ready.id]["state"]["code"])
        self.assertEqual("ready", rows[ready.id]["swap_state"]["kind"])
        self.assertEqual("action.subscription", rows[unsubscribed.id]["swap_state"]["code"])
        self.assertEqual({"code", "kind", "text"}, set(rows[ready.id]["swap_state"]))
