"""A team's registration for one tournament: what's done, what's blocked, why."""

import datetime
from typing import Any
from unittest import mock

from django.db import IntegrityError
from django.db.models import QuerySet
from django.test import TestCase
from django.utils.timezone import now
from razorpay.resources.payment import Payment

from server.core.models import Player, Team, User
from server.registration.models import RosterEntry
from server.registration.state import build_context, entry_reasons, meter, suggested_tier
from server.season.models import Season
from server.series.models import Role, SeriesRegistration, SeriesRosterInvitation
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.subscription.models import Scope, Subscription, SubscriptionPlan
from server.tests.test_eligibility import make_series
from server.tests.test_payment_accounts import PLAYER_FEE, RoutedTestCase, open_event
from server.tests.test_subscription_model import make_player
from server.tournament.models import Event, Registration
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)
from server.transaction.utils import apply_transaction
from server.utils import today


class TestRosterEntry(TestCase):
    def test_one_entry_per_player_per_team_per_event(self) -> None:
        event, team, player = open_event(), Team.objects.create(name="T"), make_player("a@x.com")
        RosterEntry.objects.create(event=event, team=team, player=player)
        with self.assertRaises(IntegrityError):
            RosterEntry.objects.create(event=event, team=team, player=player)


class TestPlayerOrderLines(RoutedTestCase):
    def order_for(self, *players: Player) -> RazorpayTransaction:
        self.tournament.teams.add(self.team)
        data = {
            "team_id": self.team.id,
            "event_id": self.event.id,
            "player_ids": [p.id for p in players],
        }
        response, _ = self.place(data, PLAYER_FEE * len(players))
        self.assertEqual(200, response.status_code, response.content)
        return RazorpayTransaction.objects.get(order_id=response.json()["order_id"])

    def test_each_player_line_carries_their_share(self) -> None:
        order = self.order_for(make_player("a@x.com"), make_player("b@x.com"))
        self.assertEqual(
            [PLAYER_FEE, PLAYER_FEE],
            list(
                RazorpayTransactionPlayer.objects.filter(transaction=order).values_list(
                    "amount", flat=True
                )
            ),
        )

    def test_each_player_line_carries_their_late_fee(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_end_date=today() - datetime.timedelta(days=2),
            player_late_penalty_end_date=today() + datetime.timedelta(days=3),
            player_late_penalty=5000,
        )
        order = self.order_for(make_player("a@x.com"), make_player("b@x.com"))
        each = PLAYER_FEE + 2 * 5000
        self.assertEqual(
            [each, each],
            list(
                RazorpayTransactionPlayer.objects.filter(transaction=order).values_list(
                    "amount", flat=True
                )
            ),
        )

    def settle(self, order: RazorpayTransaction) -> RazorpayTransaction:
        """Razorpay captured it, and the callback or webhook applies it."""
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            status="completed", payment_id=f"pay_{order.order_id}"
        )
        order.refresh_from_db()
        apply_transaction(order)
        return order

    def test_a_player_paid_for_twice_is_refunded_from_the_second_order(self) -> None:
        player = make_player("a@x.com")
        first, second = self.order_for(player), self.order_for(player)
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_1", "status": "processed"}
        ) as refund:
            self.settle(first)
            self.settle(second)
            # Replays of either change nothing more.
            self.settle(first)
            self.settle(second)
        self.assertEqual(1, refund.call_count)
        self.assertEqual(
            (f"pay_{second.order_id}", PLAYER_FEE),
            (refund.call_args.args[1], refund.call_args.args[2]["amount"]),
        )
        self.assertEqual(
            f"Already paid for in order {first.order_id}.",
            RazorpayRefund.objects.get(transaction=second).reason,
        )
        self.assertEqual(
            1, Registration.objects.filter(event=self.event, team=self.team, player=player).count()
        )

    def test_replaying_a_player_order_refunds_nothing(self) -> None:
        player = make_player("a@x.com")
        order = self.order_for(player)
        with mock.patch.object(Payment, "refund", autospec=True) as refund:
            self.settle(order)
            self.settle(order)
        refund.assert_not_called()
        self.assertTrue(Registration.objects.filter(team=self.team, player=player).exists())

    def team_fee(self, **data: Any) -> RazorpayTransaction:
        amount = data.pop("amount")
        response, _ = self.place(
            {"team_id": self.team.id, "event_id": self.event.id, **data}, amount
        )
        self.assertEqual(200, response.status_code, response.content)
        return RazorpayTransaction.objects.get(order_id=response.json()["order_id"])

    def test_a_second_full_team_fee_is_refunded(self) -> None:
        first = self.team_fee(amount=self.event.team_fee)
        second = self.team_fee(amount=self.event.team_fee)
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_1", "status": "processed"}
        ) as refund:
            self.settle(first)
            self.settle(second)
            self.settle(first)
            self.settle(second)
        self.assertEqual(1, refund.call_count)
        self.assertEqual(f"pay_{second.order_id}", refund.call_args.args[1])
        self.assertEqual(
            "Team fee already paid for this tournament.",
            RazorpayRefund.objects.get(transaction=second).reason,
        )
        self.assertIn(self.team, self.tournament.teams.all())

    def test_a_second_partial_team_fee_is_refunded(self) -> None:
        first = self.team_fee(amount=self.event.partial_team_fee, partial=True)
        second = self.team_fee(amount=self.event.partial_team_fee, partial=True)
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_1", "status": "processed"}
        ) as refund:
            self.settle(first)
            self.settle(second)
        self.assertEqual([f"pay_{second.order_id}"], [c.args[1] for c in refund.call_args_list])

    def test_a_full_team_fee_landing_after_a_partial_is_refunded(self) -> None:
        # Two admins at once: one pays the partial fee, the other the full fee.
        partial = self.team_fee(amount=self.event.partial_team_fee, partial=True)
        full = self.team_fee(amount=self.event.team_fee)
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_1", "status": "processed"}
        ) as refund:
            self.settle(partial)
            self.settle(full)
            self.settle(full)
        self.assertEqual([f"pay_{full.order_id}"], [c.args[1] for c in refund.call_args_list])
        # The partial keeps its spot; the remainder is paid as usual.
        self.assertIn(self.team, self.tournament.partial_teams.all())
        self.assertNotIn(self.team, self.tournament.teams.all())

    def test_a_partial_team_fee_then_the_rest_is_not_refunded(self) -> None:
        partial = self.team_fee(amount=self.event.partial_team_fee, partial=True)
        with mock.patch.object(Payment, "refund", autospec=True) as refund:
            self.settle(partial)
            rest = self.team_fee(amount=self.event.team_fee - self.event.partial_team_fee)
            self.settle(rest)
            self.settle(partial)
            self.settle(rest)
        refund.assert_not_called()
        self.assertIn(self.team, self.tournament.teams.all())
        self.assertNotIn(self.team, self.tournament.partial_teams.all())

    def test_paying_removes_the_entries_it_rostered(self) -> None:
        player = make_player("a@x.com")
        RosterEntry.objects.create(event=self.event, team=self.team, player=player)
        order = self.order_for(player)
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            status="completed", payment_id="pay_x"
        )
        order.refresh_from_db()
        apply_transaction(order)
        self.assertTrue(
            Registration.objects.filter(event=self.event, team=self.team, player=player).exists()
        )
        self.assertFalse(RosterEntry.objects.exists())

    def test_a_player_rostered_elsewhere_is_refunded_their_share(self) -> None:
        taken, fine = make_player("t@x.com"), make_player("f@x.com")
        order = self.order_for(taken, fine)
        rival = Team.objects.create(name="Rivals")
        Registration.objects.create(event=self.event, team=rival, player=taken)
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            status="completed", payment_id="pay_x"
        )
        order.refresh_from_db()
        with mock.patch.object(
            Payment, "refund", autospec=True, return_value={"id": "rfnd_1", "status": "processed"}
        ) as refund:
            apply_transaction(order)
        self.assertEqual(PLAYER_FEE, refund.call_args.args[2]["amount"])
        self.assertTrue(
            Registration.objects.filter(event=self.event, team=self.team, player=fine).exists()
        )
        self.assertFalse(
            Registration.objects.filter(event=self.event, team=self.team, player=taken).exists()
        )
        self.assertEqual(
            1, RazorpayRefund.objects.filter(transaction=order, line__player=taken).count()
        )

    def test_a_player_rostered_elsewhere_mid_fulfilment_is_refunded(self) -> None:
        taken, fine = make_player("t@x.com"), make_player("f@x.com")
        order = self.order_for(taken, fine)
        for player in (taken, fine):
            RosterEntry.objects.create(event=self.event, team=self.team, player=player)
        rival = Team.objects.create(name="Rivals")
        Registration.objects.create(event=self.event, team=rival, player=taken)
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            status="completed", payment_id="pay_x"
        )
        order.refresh_from_db()
        real_exists = QuerySet.exists

        def exists(qs: QuerySet[Any]) -> bool:
            # The rival registers after the "rostered elsewhere" check looked.
            return False if qs.model is Registration else real_exists(qs)

        with (
            mock.patch.object(QuerySet, "exists", autospec=True, side_effect=exists),
            mock.patch.object(
                Payment,
                "refund",
                autospec=True,
                return_value={"id": "rfnd_1", "status": "processed"},
            ) as refund,
        ):
            apply_transaction(order)
        self.assertEqual(PLAYER_FEE, refund.call_args.args[2]["amount"])
        refunds = RazorpayRefund.objects.filter(transaction=order, line__player=taken)
        self.assertEqual(1, refunds.count())
        # Flagged for review, then settled by the refund (refund_line clears the flag).
        self.assertEqual(
            "Rostered for another team before this payment completed.", refunds.get().reason
        )
        self.assertTrue(
            Registration.objects.filter(event=self.event, team=self.team, player=fine).exists()
        )
        self.assertFalse(
            Registration.objects.filter(event=self.event, team=self.team, player=taken).exists()
        )
        self.assertFalse(RosterEntry.objects.exists())


class StateTestCase(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.get(name="Season 2026-2027")
        self.series = make_series(self.season)
        self.series.event_max_players_total = 3
        self.series.event_max_players_female = 2
        self.series.event_max_players_male = 2
        self.series.save()
        self.event = open_event(
            series=self.series,
            is_subscription_needed=True,
            start_date=today() + datetime.timedelta(days=20),
        )
        self.team = Team.objects.create(name="Home")
        self.series.teams.add(self.team)
        self.admin = User.objects.create_user("admin@x.com", "admin@x.com", "pw")
        self.team.admins.add(self.admin)

    def player(
        self,
        email: str,
        match_up: str = Player.MatchupTypes.FEMALE,
        *,
        on_series: bool = True,
        tier: str | None = "regular",
        waiver: bool = True,
        entry: bool = True,
    ) -> Player:
        p = make_player(email)
        p.match_up = match_up
        p.save()
        if on_series:
            SeriesRegistration.objects.create(
                series=self.series, team=self.team, player=p, role=Role.DEFAULT
            )
        if tier:
            Subscription.objects.create(
                player=p,
                season=self.season,
                plan=SubscriptionPlan.objects.get(season=self.season, type__slug=tier),
                is_active=True,
                waiver_valid=waiver,
                start_date=self.season.start_date,
                end_date=self.season.end_date,
            )
        if entry:
            RosterEntry.objects.create(event=self.event, team=self.team, player=p)
        return p

    def reasons(self) -> dict[int, Any]:
        return entry_reasons(build_context(self.event, self.team, self.admin))


class TestEntryReasons(StateTestCase):
    def test_ready(self) -> None:
        p = self.player("a@x.com")
        self.assertEqual("ready", self.reasons()[p.id].code)

    def test_paid_is_done(self) -> None:
        p = self.player("a@x.com", entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=p)
        self.assertEqual("done.rostered", self.reasons()[p.id].code)

    def test_no_subscription_needs_action(self) -> None:
        p = self.player("a@x.com", tier=None)
        r = self.reasons()[p.id]
        self.assertEqual(("action.subscription", "action"), (r.code, r.kind))

    def test_low_tier_needs_upgrade_with_a_tier_to_buy(self) -> None:
        p = self.player("a@x.com", tier="community")
        r = self.reasons()[p.id]
        self.assertEqual("action.upgrade", r.code)
        self.assertIn("/subscription/", r.action.href)
        self.assertIn("tier=", r.action.href)

    def test_waiver_is_waiting_on_the_player(self) -> None:
        p = self.player("a@x.com", waiver=False)
        r = self.reasons()[p.id]
        self.assertEqual(("waiting.waiver", "waiting"), (r.code, r.kind))

    def test_pending_discount_request_is_awaiting_approval(self) -> None:
        p = self.player("a@x.com", tier=None)
        req = ServiceRequest.objects.create(
            user=p.user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="x",
            status=ServiceRequestStatus.PENDING,
            season=self.season,
        )
        req.service_players.add(p)
        self.assertEqual("waiting.approval", self.reasons()[p.id].code)

    def test_blank_match_up_is_profile_incomplete(self) -> None:
        p = self.player("a@x.com", match_up="")
        self.assertEqual("waiting.profile", self.reasons()[p.id].code)

    def test_pending_invite_is_waiting(self) -> None:
        p = self.player("a@x.com", on_series=False)
        SeriesRosterInvitation.objects.create(
            series=self.series, from_user=self.admin, to_player=p, team=self.team
        )
        r = self.reasons()[p.id]
        self.assertEqual(("waiting.invite", "waiting"), (r.code, r.kind))
        self.assertEqual("resend_invite", r.action.op)

    def test_expired_and_declined_invites(self) -> None:
        a = self.player("a@x.com", on_series=False)
        b = self.player("b@x.com", on_series=False)
        SeriesRosterInvitation.objects.create(
            series=self.series,
            from_user=self.admin,
            to_player=a,
            team=self.team,
            expires_on=today() - datetime.timedelta(days=1),
        )
        SeriesRosterInvitation.objects.create(
            series=self.series,
            from_user=self.admin,
            to_player=b,
            team=self.team,
            status=SeriesRosterInvitation.Status.DECLINED,
        )
        reasons = self.reasons()
        self.assertEqual("waiting.invite_expired", reasons[a.id].code)
        self.assertEqual("waiting.declined", reasons[b.id].code)

    def test_on_another_teams_series_roster_is_blocked(self) -> None:
        p = self.player("a@x.com", on_series=False)
        rival = Team.objects.create(name="Rivals")
        SeriesRegistration.objects.create(series=self.series, team=rival, player=p)
        r = self.reasons()[p.id]
        self.assertEqual(("blocked.series_other", "blocked"), (r.code, r.kind))
        self.assertIn("Rivals", r.text)

    def test_rostered_for_another_team_is_blocked(self) -> None:
        p = self.player("a@x.com")
        Registration.objects.create(
            event=self.event, team=Team.objects.create(name="Rivals"), player=p
        )
        self.assertEqual("blocked.elsewhere", self.reasons()[p.id].code)

    def test_caps_are_cumulative_in_added_order(self) -> None:
        a = self.player("a@x.com")  # female 1, total 1
        b = self.player("b@x.com")  # female 2, total 2
        c = self.player("c@x.com")  # female 3 -> over female max 2
        d = self.player("d@x.com", Player.MatchupTypes.MALE)  # total 3 -> ok
        e = self.player("e@x.com", Player.MatchupTypes.MALE)  # total 4 -> over total 3
        reasons = self.reasons()
        self.assertEqual(
            ["ready", "ready", "limit.female", "ready", "limit.total"],
            [reasons[p.id].code for p in (a, b, c, d, e)],
        )

    def test_meter_counts_paid_and_ready(self) -> None:
        self.player("a@x.com")
        paid = self.player("p@x.com", Player.MatchupTypes.MALE, entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=paid)
        ctx = build_context(self.event, self.team, self.admin)
        m = meter(ctx, entry_reasons(ctx))
        self.assertEqual(
            (2, 1, 1, 3),
            (m["total"], m["female_matching"], m["male_matching"], m["max_total"]),
        )

    def hold(self, player: Player) -> RazorpayTransaction:
        other = User.objects.create_user("o@x.com", "o@x.com", "pw")
        order = RazorpayTransaction.objects.create(
            order_id="order_h",
            amount=1,
            currency="INR",
            status="created",
            user=other,
            event=self.event,
            team=self.team,
            type="player-reg",
        )
        RosterEntry.objects.filter(player=player).update(held_by_order=order)
        return order

    def test_held_by_another_admins_open_order(self) -> None:
        p = self.player("a@x.com")
        self.hold(p)
        self.assertEqual("progress.held", self.reasons()[p.id].code)

    def test_a_stale_hold_does_not_count(self) -> None:
        p = self.player("a@x.com")
        order = self.hold(p)
        RazorpayTransaction.objects.filter(pk=order.pk).update(
            payment_date=now() - datetime.timedelta(minutes=21)
        )
        self.assertEqual("ready", self.reasons()[p.id].code)

    def test_rostering_closed(self) -> None:
        p = self.player("a@x.com")
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_end_date=today() - datetime.timedelta(days=1),
            player_late_penalty_end_date=None,
        )
        self.event.refresh_from_db()
        self.assertEqual("timing.closed", self.reasons()[p.id].code)

    def test_suggested_tier_is_the_cheapest_that_covers_playing(self) -> None:
        p = make_player("n@x.com")
        tier = suggested_tier(p, self.season, Scope.PLAY_CHAMPIONSHIPS)
        cheapest = min(
            (
                plan
                for plan in SubscriptionPlan.objects.filter(season=self.season, is_available=True)
                if plan.type.allows(Scope.PLAY_CHAMPIONSHIPS) and not plan.type.requires_grant
            ),
            key=lambda plan: plan.amount,
        )
        self.assertEqual((cheapest.type.slug, cheapest.amount), tier)

    def paid(self, email: str, match_up: str = Player.MatchupTypes.MALE) -> Player:
        p = self.player(email, match_up, entry=False)
        Registration.objects.create(event=self.event, team=self.team, player=p)
        return p

    def test_a_total_cap_of_zero_is_full(self) -> None:
        self.series.event_max_players_total = 0
        self.series.save()
        p = self.player("a@x.com")
        self.assertEqual("limit.total", self.reasons()[p.id].code)

    def test_a_held_entry_takes_its_spot(self) -> None:
        self.paid("p1@x.com")
        self.paid("p2@x.com")
        x = self.player("x@x.com")
        y = self.player("y@x.com")
        self.hold(x)
        ctx = build_context(self.event, self.team, self.admin)
        reasons = entry_reasons(ctx)
        self.assertEqual(["progress.held", "limit.total"], [reasons[p.id].code for p in (x, y)])
        self.assertEqual(3, meter(ctx, reasons)["total"])

    def test_closed_rostering_comes_before_asking_for_a_subscription(self) -> None:
        p = self.player("a@x.com", tier=None)
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_end_date=today() - datetime.timedelta(days=1),
            player_late_penalty_end_date=None,
        )
        self.event.refresh_from_db()
        self.assertEqual("timing.closed", self.reasons()[p.id].code)

    def test_a_full_roster_comes_before_asking_for_a_subscription(self) -> None:
        self.paid("p1@x.com")
        self.paid("p2@x.com")
        self.paid("p3@x.com", Player.MatchupTypes.FEMALE)
        p = self.player("a@x.com", tier=None)
        self.assertEqual("limit.total", self.reasons()[p.id].code)

    def test_a_subscription_can_be_sorted_before_rostering_opens(self) -> None:
        p = self.player("a@x.com", tier=None)
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_start_date=today() + datetime.timedelta(days=2)
        )
        self.event.refresh_from_db()
        self.assertEqual("action.subscription", self.reasons()[p.id].code)

    def test_not_open_yet_once_everything_else_is_fine(self) -> None:
        p = self.player("a@x.com")
        Event.objects.filter(pk=self.event.pk).update(
            player_registration_start_date=today() + datetime.timedelta(days=2)
        )
        self.event.refresh_from_db()
        self.assertEqual("timing.not_open", self.reasons()[p.id].code)

    def test_a_full_series_roster_cannot_take_an_invite(self) -> None:
        self.series.series_roster_max_players = 1
        self.series.save()
        self.player("on@x.com", entry=False)
        p = self.player("off@x.com", on_series=False)
        r = self.reasons()[p.id]
        self.assertEqual(("limit.series_roster", "limit", None), (r.code, r.kind, r.action))
        self.assertIn("1/1", r.text)

    def test_a_hold_added_after_a_ready_row_still_takes_its_spot(self) -> None:
        self.paid("p1@x.com")
        self.paid("p2@x.com")
        y = self.player("y@x.com")
        x = self.player("x@x.com")
        self.hold(x)
        ctx = build_context(self.event, self.team, self.admin)
        reasons = entry_reasons(ctx)
        self.assertEqual(["limit.total", "progress.held"], [reasons[p.id].code for p in (y, x)])
        self.assertEqual(3, meter(ctx, reasons)["total"])

    def test_an_accepted_invite_with_no_series_registration_invites_again(self) -> None:
        # Accepted, then taken off the series roster.
        p = self.player("a@x.com", on_series=False)
        SeriesRosterInvitation.objects.create(
            series=self.series,
            from_user=self.admin,
            to_player=p,
            team=self.team,
            status=SeriesRosterInvitation.Status.ACCEPTED,
        )
        r = self.reasons()[p.id]
        self.assertEqual(("action.invite", "invite"), (r.code, r.action.op))

    def test_no_plan_they_can_buy_waits_on_a_discount_request(self) -> None:
        # Only the discounted tier plays, and it needs an approval they don't have.
        self.season.plans.filter(type__requires_grant=False).update(is_available=False)
        p = self.player("a@x.com", tier=None)
        r = self.reasons()[p.id]
        self.assertEqual(
            (
                "waiting.approval",
                "waiting",
                "Needs a discounted subscription — the player must request it",
                None,
            ),
            (r.code, r.kind, r.text, r.action),
        )
