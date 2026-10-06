"""Every order type, from the order endpoint to the callback, Razorpay mocked."""

import datetime
from typing import Any
from unittest import mock

from server.core.models import Player, Team
from server.forms.models import Form, FormResponse
from server.season.models import Season
from server.series.models import Role, Series, SeriesRegistration
from server.subscription.models import Subscription, SubscriptionPlan
from server.tests.base import ApiBaseTestCase, fake_id, fake_order
from server.tournament.models import Event, Registration, Tournament
from server.transaction.models import RazorpayTransaction
from server.utils import today

from .test_eligibility import make_series
from .test_subscription_model import make_player

TEAM_FEE = 500000
PARTIAL_FEE = 200000
PLAYER_FEE = 100000


class TestPaymentFlows(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.login()
        day = today()
        self.team = Team.objects.create(name="Payers")
        self.team.admins.add(self.user)
        self.open_event = Event.objects.create(
            title="Open event",
            start_date=day + datetime.timedelta(days=20),
            end_date=day + datetime.timedelta(days=22),
            team_registration_start_date=day - datetime.timedelta(days=1),
            team_registration_end_date=day + datetime.timedelta(days=10),
            player_registration_start_date=day - datetime.timedelta(days=1),
            player_registration_end_date=day + datetime.timedelta(days=10),
            team_fee=TEAM_FEE,
            partial_team_fee=PARTIAL_FEE,
            player_fee=PLAYER_FEE,
        )
        self.open_tournament = Tournament.objects.create(event=self.open_event)
        self.season = Season.objects.get(name="Season 2026-2027")

    def rostered_for_series(self, series: Series, email: str, slug: str, role: str) -> Player:
        player = make_player(email)
        Subscription.objects.create(
            player=player,
            season=self.season,
            plan=SubscriptionPlan.objects.get(season=self.season, type__slug=slug),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=self.season.start_date,
            end_date=self.season.end_date,
        )
        SeriesRegistration.objects.create(series=series, team=self.team, player=player, role=role)
        return player

    def order(self, data: dict[str, Any], amount: int) -> RazorpayTransaction:
        with mock.patch(
            "server.transaction.client.razorpay.create_order", return_value=fake_order(amount)
        ) as create_order:
            response = self.client.post(
                "/api/transactions/razorpay", data=data, content_type="application/json"
            )
        self.assertEqual(200, response.status_code, response.content)
        create_order.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY, account=None)
        return RazorpayTransaction.objects.get(order_id=response.json()["order_id"])

    def pay(self, order_id: str) -> None:
        with mock.patch("server.transaction.client.razorpay.verify_payment", return_value=True):
            response = self.client.post(
                "/api/transactions/razorpay/callback",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": f"pay_{fake_id(16)}",
                    "razorpay_signature": fake_id(64),
                },
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code, response.content)
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(RazorpayTransaction.TransactionStatusChoices.COMPLETED, transaction.status)

    def test_a_paid_team_registration_registers_the_team(self) -> None:
        data = {"team_id": self.team.id, "event_id": self.open_event.id}
        transaction = self.order(data, TEAM_FEE)
        self.assertEqual(
            RazorpayTransaction.TransactionTypeChoices.TEAM_REGISTRATION, transaction.type
        )
        self.assertNotIn(self.team, self.open_tournament.teams.all())

        self.pay(transaction.order_id)

        self.assertIn(self.team, self.open_tournament.teams.all())
        self.assertNotIn(self.team, self.open_tournament.partial_teams.all())

    def test_a_partial_then_full_registration_moves_the_team_across(self) -> None:
        data = {"team_id": self.team.id, "event_id": self.open_event.id}
        partial = self.order({**data, "partial": True}, PARTIAL_FEE)
        self.assertEqual(
            RazorpayTransaction.TransactionTypeChoices.PARTIAL_TEAM_REGISTRATION, partial.type
        )
        self.pay(partial.order_id)
        self.assertIn(self.team, self.open_tournament.partial_teams.all())
        self.assertNotIn(self.team, self.open_tournament.teams.all())

        # The rest of the fee, and the team is fully in.
        rest = self.order(data, TEAM_FEE - PARTIAL_FEE)
        self.pay(rest.order_id)
        self.assertIn(self.team, self.open_tournament.teams.all())
        self.assertNotIn(self.team, self.open_tournament.partial_teams.all())

    def test_a_paid_player_registration_rosters_everyone_on_it(self) -> None:
        self.open_tournament.teams.add(self.team)
        friend = make_player("friend@example.com")
        data = {
            "team_id": self.team.id,
            "event_id": self.open_event.id,
            "player_ids": [self.player.id, friend.id],
        }
        transaction = self.order(data, 2 * PLAYER_FEE)
        self.assertFalse(Registration.objects.filter(event=self.open_event).exists())

        self.pay(transaction.order_id)

        self.assertEqual(
            {self.player.id, friend.id},
            set(
                Registration.objects.filter(event=self.open_event, team=self.team).values_list(
                    "player_id", flat=True
                )
            ),
        )

    def test_a_player_registration_checks_subscription_before_any_money(self) -> None:
        self.open_tournament.teams.add(self.team)
        self.open_event.is_subscription_needed = True
        self.open_event.save()
        data = {
            "team_id": self.team.id,
            "event_id": self.open_event.id,
            "player_ids": [self.player.id],
        }
        with mock.patch("server.transaction.client.razorpay.create_order") as create_order:
            response = self.client.post(
                "/api/transactions/razorpay", data=data, content_type="application/json"
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Subscription missing", response.json()["message"])
        create_order.assert_not_called()

        # With a Regular subscription for the event's season, the order goes ahead.
        season = Season.containing(self.open_event.start_date)
        assert season is not None  # noqa: S101 - narrows the type
        Subscription.objects.create(
            player=self.player,
            season=season,
            plan=SubscriptionPlan.objects.get(season=season, type__slug="regular"),
            is_active=True,
            waiver_valid=True,
            coc_agreed=True,
            start_date=season.start_date,
            end_date=season.end_date,
        )
        self.order(data, PLAYER_FEE)

    def test_paying_for_series_staff_skips_caps_but_not_the_playing_count(self) -> None:
        self.open_tournament.teams.add(self.team)
        series = make_series(self.season)
        series.event_max_players_total = 1
        series.save()
        self.open_event.series = series
        self.open_event.save()

        # The one playing spot is already taken.
        playing = self.rostered_for_series(series, "playing@example.com", "regular", Role.DEFAULT)
        Registration.objects.create(
            event=self.open_event, team=self.team, player=playing, is_playing=True
        )

        coach = self.rostered_for_series(series, "coach@example.com", "community", Role.COACH)
        data = {
            "team_id": self.team.id,
            "event_id": self.open_event.id,
            "player_ids": [coach.id],
        }
        transaction = self.order(data, PLAYER_FEE)
        self.pay(transaction.order_id)

        registration = Registration.objects.get(event=self.open_event, player=coach)
        self.assertFalse(registration.is_playing)
        self.assertEqual(
            1, Registration.objects.filter(event=self.open_event, is_playing=True).count()
        )

    def test_paid_series_staff_role_is_accepted_though_it_cannot_play(self) -> None:
        self.open_tournament.teams.add(self.team)
        series = make_series(self.season)
        series.event_max_players_total = 10
        series.save()
        self.open_event.series = series
        self.open_event.save()

        coach = self.rostered_for_series(series, "coach@example.com", "community", Role.COACH)
        data = {
            "team_id": self.team.id,
            "event_id": self.open_event.id,
            "player_ids": [coach.id],
        }
        self.order(data, PLAYER_FEE)

    def test_a_community_tier_playing_role_is_still_refused(self) -> None:
        self.open_tournament.teams.add(self.team)
        series = make_series(self.season)
        series.event_max_players_total = 10
        series.save()
        self.open_event.series = series
        self.open_event.save()

        player = self.rostered_for_series(series, "player@example.com", "community", Role.DEFAULT)
        data = {
            "team_id": self.team.id,
            "event_id": self.open_event.id,
            "player_ids": [player.id],
        }
        with mock.patch("server.transaction.client.razorpay.create_order") as create_order:
            response = self.client.post(
                "/api/transactions/razorpay", data=data, content_type="application/json"
            )
        self.assertEqual(400, response.status_code)
        self.assertIn("does not cover playing here", response.json()["message"])
        create_order.assert_not_called()

    def test_a_paid_form_response_is_marked_paid(self) -> None:
        form = Form.objects.create(
            title="Camp sign-up",
            slug="camp-sign-up",
            fields=[{"key": "size", "label": "Size", "type": "text", "required": True}],
            payment_amount=150000,
            is_active=True,
            created_by=self.user,
        )
        with mock.patch(
            "server.transaction.client.razorpay.create_order", return_value=fake_order(150000)
        ):
            response = self.client.post(
                f"/api/forms/{form.slug}/responses",
                data={"answers": {"size": "M"}},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("payment_required", response.json()["status"])
        answer = FormResponse.objects.get(form=form)
        self.assertFalse(answer.is_paid)
        transaction = answer.transaction
        assert transaction is not None  # noqa: S101 - narrows the type
        self.assertEqual(RazorpayTransaction.TransactionTypeChoices.FORM_PAYMENT, transaction.type)

        self.pay(transaction.order_id)

        answer.refresh_from_db()
        self.assertTrue(answer.is_paid)
