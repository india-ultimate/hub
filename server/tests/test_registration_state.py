"""A team's registration for one tournament: what's done, what's blocked, why."""

import datetime
from typing import Any
from unittest import mock

from django.db import IntegrityError
from django.db.models import QuerySet
from django.test import TestCase
from razorpay.resources.payment import Payment

from server.core.models import Player, Team
from server.registration.models import RosterEntry
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
