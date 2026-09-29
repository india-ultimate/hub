import datetime
import json
import uuid
from pathlib import Path
from typing import Any
from unittest import mock

from django.core import mail
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.models import Q
from django.test import Client
from django.test.client import MULTIPART_CONTENT
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from server.core.accounts import find_login_user
from server.core.models import Guardianship, Player, UCPerson, User
from server.duplicates.merge import merge_accounts
from server.duplicates.models import EmailAlias
from server.passkey_utils import ClientResponse
from server.season.models import Season
from server.subscription import sponsorship
from server.subscription.models import Subscription, SubscriptionPlan, SubscriptionType
from server.tests.base import ApiBaseTestCase, create_pool, fake_id, fake_order, start_tournament
from server.tests.test_subscription import SubscriptionStatusTestCase
from server.tournament.models import Match, UCRegistration
from server.transaction.client.phonepe import update_transaction
from server.transaction.models import (
    ManualTransaction,
    PhonePeTransaction,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)
from server.utils import today


class TestLogin(ApiBaseTestCase):
    def test_login(self) -> None:
        c = Client()
        response = c.post(
            "/api/login",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(self.username, data["username"])

    def test_logout(self) -> None:
        c = Client()
        response = c.post(
            "/api/login",
            data={"username": self.username, "password": self.password},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        response = c.post("/api/logout", content_type="application/json")
        self.assertEqual(200, response.status_code)


class TestPasskey(ApiBaseTestCase):
    def test_enabling_one_tap_does_not_need_a_second_login_step(self) -> None:
        self.client.force_login(self.user)
        with mock.patch("server.api.passkey_client.finish_registration") as finish:
            finish.return_value = ClientResponse(data="{}")
            response = self.client.post(
                "/api/passkey/create/finish",
                data={"passkey_request": "{}"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)

    def test_a_passkey_on_a_merged_away_account_signs_in_to_the_keeper(self) -> None:
        gone = User.objects.create(username="gone@foo.com", email="gone@foo.com")
        middle = User.objects.create(username="middle@foo.com", email="middle@foo.com")
        gone_id = gone.id
        merge_accounts(middle, [gone], dry_run=False)
        merge_accounts(self.user, [middle], dry_run=False)

        def passkey_login() -> Any:
            with mock.patch("server.api.passkey_client.finish_login") as finish:
                finish.return_value = ClientResponse(data="{}", user_id=str(gone_id))
                return self.client.post(
                    "/api/passkey/login/finish",
                    data={"passkey_request": "{}"},
                    content_type="application/json",
                )

        response = passkey_login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], self.username)

        self.user.delete()
        self.assertEqual(passkey_login().status_code, 400)

    def test_a_deactivated_account_cannot_use_its_passkey(self) -> None:
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        with mock.patch("server.api.passkey_client.finish_login") as finish:
            finish.return_value = ClientResponse(data="{}", user_id=str(self.user.id))
            response = self.client.post(
                "/api/passkey/login/finish",
                data={"passkey_request": "{}"},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)


class TestRegistration(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_register_me(self) -> None:
        c = self.client
        self.user.player_profile.delete()
        data = {
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "O",
            "other_gender": "Non-Binary",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
            "match_up": "F",
        }
        response = c.post(
            "/api/registration",
            data=data,
            content_type="application/json",
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertEqual(self.user.id, response_data["user"])
        self.user.refresh_from_db()

    def test_edit_registration(self) -> None:
        c = self.client

        self.assertEqual("", self.player.user.phone)
        self.assertEqual("John", self.player.user.first_name)
        self.assertEqual("", self.player.city)

        data = {
            "player_id": self.player.id,
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
        }
        response = c.put(
            "/api/registration",
            data=data,
            content_type="application/json",
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertEqual(self.user.id, response_data["user"])

    def test_a_player_cannot_make_themselves_sponsored(self) -> None:
        """sponsored decides the subscription fee and is an admin decision.
        It must not be settable by the person who would pay it."""
        self.assertFalse(self.player.sponsored)

        response = self.client.put(
            "/api/registration",
            data={
                "player_id": self.player.id,
                "phone": "+1234567890",
                "date_of_birth": "1990-01-01",
                "gender": "F",
                "match_up": "F",
                "city": "Bangalore",
                "first_name": "Nora",
                "last_name": "Quinn",
                "sponsored": True,
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code)
        self.player.refresh_from_db()
        self.assertFalse(self.player.sponsored, "a player set their own fee discount")

    def test_a_player_cannot_choose_their_iu_id(self) -> None:
        """The number is printed on waivers and certificates. A self-chosen
        one -- IU-22-0001 to look like a founding member -- is forgery."""
        self.player.iu_id = "IU-26-0042"
        self.player.save(update_fields=["iu_id"])

        response = self.client.put(
            "/api/registration",
            data={
                "player_id": self.player.id,
                "phone": "+1234567890",
                "date_of_birth": "1990-01-01",
                "gender": "F",
                "match_up": "F",
                "city": "Bangalore",
                "first_name": "Nora",
                "last_name": "Quinn",
                "iu_id": "IU-22-0001",
            },
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code)
        self.player.refresh_from_db()
        self.assertEqual(
            "IU-26-0042",
            self.player.iu_id,
            "a player chose their own IU ID",
        )

    def test_a_player_cannot_mark_themselves_imported(self) -> None:
        self.assertFalse(self.player.imported_data)

        self.client.put(
            "/api/registration",
            data={
                "player_id": self.player.id,
                "phone": "+1234567890",
                "date_of_birth": "1990-01-01",
                "gender": "F",
                "match_up": "F",
                "city": "Bangalore",
                "first_name": "Nora",
                "last_name": "Quinn",
                "imported_data": True,
            },
            content_type="application/json",
        )

        self.player.refresh_from_db()
        self.assertFalse(self.player.imported_data)

    def test_register_others(self) -> None:
        c = self.client
        self.user.player_profile.delete()
        data = {
            "email": "foo@email.com",
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
        }
        response = c.post(
            "/api/registration/others",
            data=data,
            content_type="application/json",
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertLess(self.user.id, response_data["user"])
        user = User.objects.get(id=response_data["user"])
        self.assertEqual(user.username, data["email"])
        self.assertEqual(user.email, data["email"])

    def test_register_others_minor_fail(self) -> None:
        c = self.client
        self.user.player_profile.delete()

        dob = now() - datetime.timedelta(days=15 * 365)

        data = {
            "email": "foo@email.com",
            "phone": "+1234567890",
            "date_of_birth": dob.date(),
            "gender": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
        }
        response = c.post(
            "/api/registration/others",
            data=data,
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)

    def test_register_ward_non_minor_fail(self) -> None:
        c = self.client
        self.user.player_profile.delete()

        data = {
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
            "relation": "MO",
        }
        response = c.post(
            "/api/registration/ward",
            data=data,
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)

    def test_register_ward(self) -> None:
        c = self.client
        self.user.player_profile.delete()

        # ~15 years old
        dob = now() - datetime.timedelta(days=15 * 365)

        data = {
            "phone": "+1234567890",
            "date_of_birth": str(dob.date()),
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
            "relation": "MO",
        }
        response = c.post(
            "/api/registration/ward",
            data=data,
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        response_data = response.json()
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertLess(self.user.id, response_data["user"])
        self.assertEqual(self.user.id, response_data["guardian"])
        user = User.objects.get(id=response_data["user"])
        self.assertEqual(user.username, "nora-quinn")
        self.assertEqual(user.email, "nora-quinn")

    def test_register_guardian_non_minor_fail(self) -> None:
        c = self.client
        self.user.player_profile.delete()

        data = {
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
            "guardian_first_name": "Mora",
            "guardian_last_name": "Saiyyan",
            "guardian_email": "mora@gmail.com",
            "guardian_phone": "+123321456654",
            "relation": "MO",
        }
        response = c.post(
            "/api/registration/guardian",
            data=data,
            content_type="application/json",
        )
        self.assertEqual(400, response.status_code)

    def test_register_guardian(self) -> None:
        c = self.client
        self.user.player_profile.delete()

        # ~15 years old
        dob = now() - datetime.timedelta(days=15 * 365)

        data = {
            "phone": "+1234567890",
            "date_of_birth": str(dob.date()),
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
            "guardian_first_name": "Mora",
            "guardian_last_name": "Saiyyan",
            "guardian_email": "mora@gmail.com",
            "guardian_phone": "+123321456654",
            "relation": "MO",
        }
        response = c.post(
            "/api/registration/guardian",
            data=data,
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        response_data = response.json()
        print(response_data)
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertEqual(self.user.id, response_data["user"])
        self.assertLess(self.user.id, response_data["guardian"])
        self.user.refresh_from_db()
        guardian_user = self.user.player_profile.guardianship.user
        self.assertEqual(guardian_user.email, data["guardian_email"])
        self.assertEqual(guardian_user.phone, data["guardian_phone"])
        self.assertEqual(guardian_user.first_name, data["guardian_first_name"])
        self.assertEqual(guardian_user.last_name, data["guardian_last_name"])


class TestRegisteringAnAbsorbedAddress(ApiBaseTestCase):
    """An address a merge absorbed signs in to the account that absorbed it.
    Registering someone with it must find that account, not make a new one
    that would capture the address's sign in from then on."""

    def setUp(self) -> None:
        super().setUp()
        self.owner = User.objects.create(
            username="owner@x.com", email="owner@x.com", first_name="Old", last_name="Owner"
        )
        EmailAlias.objects.create(email="gone@x.com", user=self.owner)
        self.client.force_login(self.user)
        self.minor = str((now() - datetime.timedelta(days=15 * 365)).date())
        self.player_fields = {
            "phone": "+1234567890",
            "gender": "F",
            "match_up": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
        }

    def post(self, path: str, data: dict[str, str]) -> Any:
        return self.client.post(path, data=data, content_type="application/json")

    def test_registering_others_finds_the_account(self) -> None:
        users = User.objects.count()
        response = self.post(
            "/api/registration/others",
            {**self.player_fields, "email": " Gone@x.com ", "date_of_birth": "1990-01-01"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["user"], self.owner.id)
        self.assertEqual(User.objects.count(), users)
        self.assertEqual(find_login_user("gone@x.com"), self.owner)

    def test_registering_a_ward_finds_the_account(self) -> None:
        users = User.objects.count()
        response = self.post(
            "/api/registration/ward",
            {
                **self.player_fields,
                "email": "gone@x.com",
                "date_of_birth": self.minor,
                "relation": "MO",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["user"], self.owner.id)
        self.assertEqual(response.json()["guardian"], self.user.id)
        self.assertEqual(User.objects.count(), users)

    def test_registering_a_guardian_finds_the_account(self) -> None:
        self.user.player_profile.delete()
        users = User.objects.count()
        response = self.post(
            "/api/registration/guardian",
            {
                **self.player_fields,
                "date_of_birth": self.minor,
                "guardian_first_name": "Mora",
                "guardian_last_name": "Saiyyan",
                "guardian_email": "gone@x.com",
                "guardian_phone": "+123321456654",
                "relation": "MO",
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["guardian"], self.owner.id)
        self.assertEqual(User.objects.count(), users)

    def test_your_own_old_address_is_you_on_the_ward_form(self) -> None:
        EmailAlias.objects.create(email="mine.old@x.com", user=self.user)
        self.user.player_profile.delete()
        response = self.post(
            "/api/registration/ward",
            {
                **self.player_fields,
                "email": "mine.old@x.com",
                "date_of_birth": self.minor,
                "relation": "MO",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("players form", response.json()["message"])
        self.assertFalse(Guardianship.objects.filter(user=self.user).exists())

    def test_your_own_old_address_is_you_on_the_guardian_form(self) -> None:
        EmailAlias.objects.create(email="mine.old@x.com", user=self.user)
        self.user.player_profile.delete()
        response = self.post(
            "/api/registration/guardian",
            {
                **self.player_fields,
                "date_of_birth": self.minor,
                "guardian_first_name": "John",
                "guardian_last_name": "Williamson",
                "guardian_email": "mine.old@x.com",
                "guardian_phone": "+123321456654",
                "relation": "MO",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("guardians form", response.json()["message"])
        self.assertFalse(Guardianship.objects.filter(user=self.user).exists())


class TestPlayers(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_get_players(self) -> None:
        c = self.client
        response = c.get(
            "/api/players",
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        user_data = data[0]
        self.assertIn("city", user_data)
        self.assertIn("state_ut", user_data)
        self.assertEqual("username@foo.com", user_data["email"])
        self.assertNotIn("subscription", user_data)
        self.assertNotIn("guardian", user_data)

    def test_get_players_staff(self) -> None:
        c = self.client
        self.user.is_staff = True
        self.user.save()
        response = c.get("/api/players?full_schema=1", content_type="application/json")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        user_data = data[0]
        self.assertIn("city", user_data)
        self.assertIn("state_ut", user_data)
        self.assertEqual("username@foo.com", user_data["email"])
        self.assertIn("subscription", user_data)
        self.assertIn("guardian", user_data)

        response = c.get("/api/players", content_type="application/json")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        user_data = data[0]
        self.assertIn("city", user_data)
        self.assertIn("state_ut", user_data)
        self.assertEqual("username@foo.com", user_data["email"])
        self.assertNotIn("subscription", user_data)
        self.assertNotIn("guardian", user_data)

    def test_get_players_query_count_does_not_grow_with_player_count(self) -> None:
        # The plain (non-staff) shape: this is the unpaginated list every
        # visitor hits, so it must not do more work per player added.
        c = self.client

        with CaptureQueriesContext(connection) as ctx:
            response = c.get("/api/players", content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()))
        baseline = len(ctx.captured_queries)

        for i in range(2):
            extra_user = User.objects.create(
                username=f"extra{i}@foo.com", email=f"extra{i}@foo.com"
            )
            Player.objects.create(user=extra_user, date_of_birth="1995-01-01")

        with self.assertNumQueries(baseline):
            response = c.get("/api/players", content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertEqual(3, len(response.json()))


class TestPayment(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.on_sale = Season.objects.get(name="Season 2026-2027")

    def order(self, items: list[dict[str, Any]], amount: int) -> Any:
        with mock.patch(
            "server.transaction.client.razorpay.create_order",
            return_value=fake_order(amount),
        ) as f:
            response = self.client.post(
                "/api/transactions/razorpay",
                data={"season_id": self.on_sale.id, "items": items},
                content_type="application/json",
            )
        self.create_order = f
        return response

    def test_create_order_no_player(self) -> None:
        response = self.order([{"player_id": 200, "plan_type": "regular"}], 0)
        self.assertEqual(422, response.status_code)
        self.assertEqual(
            "Some players couldn't be found in the DB: [200]", response.json()["message"]
        )

    def test_create_order_player_exists(self) -> None:
        player = self.player
        amount = 75000
        response = self.order([{"player_id": player.id, "plan_type": "regular"}], amount)
        self.create_order.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("order_id", order_data)
        transaction = RazorpayTransaction.objects.get(order_id=order_data["order_id"])
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())
        # Saved with Razorpay's own order status, as production stores it.
        self.assertEqual("created", transaction.status)
        self.assertEqual(self.on_sale.start_date, transaction.start_date)
        self.assertEqual(self.on_sale.end_date, transaction.end_date)
        self.assertEqual(self.on_sale, transaction.season)
        self.assertFalse(Subscription.objects.filter(player=player).exists())

    def test_create_order_sponsored_player_exists(self) -> None:
        player = self.player
        sponsorship.grant(player, self.on_sale)
        amount = 30000
        response = self.order([{"player_id": player.id, "plan_type": "discounted"}], amount)
        self.create_order.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())

    def test_create_order_group_subscription_missing_players(self) -> None:
        player_ids = [200, 220, 230, 225]
        response = self.order([{"player_id": id_, "plan_type": "regular"} for id_ in player_ids], 0)
        self.assertEqual(422, response.status_code)
        self.assertEqual(
            "Some players couldn't be found in the DB: [200, 220, 225, 230]",
            response.json()["message"],
        )

    def test_create_order_group_subscription(self) -> None:
        player_ids = [200, 220, 230, 225]

        for id_ in player_ids:
            username = str(uuid.uuid4())[:8]
            user = User.objects.create(username=username)
            date_of_birth = "2001-01-01"
            Player.objects.create(id=id_, user=user, date_of_birth=date_of_birth)

        amount = 75000 * len(player_ids)
        response = self.order(
            [{"player_id": id_, "plan_type": "regular"} for id_ in player_ids], amount
        )
        self.create_order.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        transaction = RazorpayTransaction.objects.get(order_id=response.json()["order_id"])
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(self.on_sale.start_date, transaction.start_date)
        self.assertEqual(self.on_sale.end_date, transaction.end_date)
        self.assertEqual(set(player_ids), {p.id for p in transaction.players.all()})
        self.assertFalse(Subscription.objects.filter(player_id__in=player_ids).exists())
        # Saved with Razorpay's own order status, as production stores it.
        self.assertEqual("created", transaction.status)

    def paid_order(self, members: list[Player], slug: str = "regular") -> RazorpayTransaction:
        """A pending order with one priced line per person."""
        plan = SubscriptionPlan.objects.get(
            season=self.on_sale, type=SubscriptionType.objects.get(slug=slug)
        )
        order = fake_order(plan.amount * len(members))
        order.update(
            {
                "start_date": self.on_sale.start_date,
                "end_date": self.on_sale.end_date,
                "user": self.user,
                "season": self.on_sale,
            }
        )
        transaction = RazorpayTransaction.create_from_order_data(order)
        for member in members:
            RazorpayTransactionPlayer.objects.create(
                transaction=transaction, player=member, plan=plan, amount=plan.amount
            )
        return transaction

    def pay(self, transaction: RazorpayTransaction) -> Any:
        with mock.patch("server.transaction.client.razorpay.verify_payment", return_value=True):
            return self.client.post(
                "/api/transactions/razorpay/callback",
                data={
                    "razorpay_order_id": transaction.order_id,
                    "razorpay_payment_id": f"pay_{fake_id(16)}",
                    "razorpay_signature": f"{fake_id(64)}",
                },
                content_type="application/json",
            )

    def test_payment_success(self) -> None:
        player = self.player
        transaction = self.paid_order([player])
        self.assertFalse(Subscription.objects.filter(player=player).exists())

        response = self.pay(transaction)

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(player.id, data[0]["id"])
        self.assertTrue(data[0]["subscription"]["is_active"])

        transaction.refresh_from_db()
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )
        # The signature is written to the column it belongs in.
        self.assertTrue(transaction.payment_signature)

        subscription = Subscription.objects.get(player=player, season=self.on_sale)
        self.assertTrue(subscription.is_active)
        self.assertEqual(self.on_sale.start_date, subscription.start_date)
        self.assertEqual(self.on_sale.end_date, subscription.end_date)
        self.assertEqual(75000, subscription.amount_paid)
        player.refresh_from_db()
        self.assertTrue(player.iu_id)

    def test_a_replayed_callback_changes_nothing(self) -> None:
        transaction = self.paid_order([self.player])
        self.assertEqual(200, self.pay(transaction).status_code)
        transaction.refresh_from_db()
        first_payment_id = transaction.payment_id

        # Razorpay's checkout can fire the callback twice, and the buyer can
        # double-click. A settled order is not acted on again.
        response = self.pay(transaction)

        self.assertEqual(200, response.status_code)
        self.assertEqual(self.player.id, response.json()[0]["id"])
        transaction.refresh_from_db()
        self.assertEqual(first_payment_id, transaction.payment_id)
        self.assertEqual(1, Subscription.objects.filter(player=self.player).count())

    def test_payment_success_group_subscription(self) -> None:
        players = []
        for _ in range(4):
            user_ = User.objects.create(username=str(uuid.uuid4())[:8])
            players.append(Player.objects.create(user=user_, date_of_birth="2001-01-01"))

        transaction = self.paid_order(players)
        response = self.pay(transaction)

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(players), len(data))
        for player_data in data:
            subscription = player_data["subscription"]
            self.assertTrue(subscription["is_active"])
            self.assertEqual(str(self.on_sale.start_date), subscription["start_date"])
            self.assertEqual(str(self.on_sale.end_date), subscription["end_date"])

        transaction.refresh_from_db()
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )
        self.assertEqual(
            len(players), Subscription.objects.filter(season=self.on_sale, is_active=True).count()
        )

    def test_list_transactions(self) -> None:
        c = self.client

        # Create player and wards for current user
        users = []
        players = [self.player]
        for _i in range(3):
            username = str(uuid.uuid4())[:8]
            user_ = User.objects.create(username=username)
            users.append(user_)

            date_of_birth = "2001-01-01"
            player = Player.objects.create(user=user_, date_of_birth=date_of_birth)
            players.append(player)

        # Make players[1] a ward
        Guardianship.objects.create(relation="LG", user=self.user, player=players[1])

        orders = set()

        # Create transaction made by current user
        order = fake_order(140000)
        order.update(user=self.user, players=players[2:], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction for current user's player
        order = fake_order(70000)
        order.update(user=users[0], players=players[:1], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction for current user's ward
        order = fake_order(70000)
        order.update(user=users[2], players=players[1:2], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction made by another user
        order = fake_order(140000)
        order.update(user=users[2], players=players[2:], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)

        response = c.get(
            "/api/transactions/",
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        response_data = response.json()

        self.assertEqual(len(orders), len(response_data))
        self.assertEqual(orders, {t["transaction_id"] for t in response_data})

    def test_razorpay_failures(self) -> None:
        player = self.player
        c = self.client
        with mock.patch("server.transaction.client.razorpay.create_order", return_value=None):
            response = c.post(
                "/api/transactions/razorpay",
                data={
                    "season_id": self.on_sale.id,
                    "items": [{"player_id": player.id, "plan_type": "regular"}],
                },
                content_type="application/json",
            )

        self.assertEqual(502, response.status_code)
        self.assertIn(b"Razorpay", response.content)

    def test_update_phonepe_transaction(self) -> None:
        transaction = PhonePeTransaction.objects.create(
            user=self.user, transaction_id=uuid.uuid4(), amount=10000
        )
        transaction.players.add(self.player)
        update_transaction(transaction, "ERROR")
        self.assertFalse(Subscription.objects.filter(player=self.player).exists())


class TestVaccination(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_not_vaccinated(self) -> None:
        c = self.client
        data = {
            "is_vaccinated": False,
            "explain_not_vaccinated": "I do not believe in this shit!",
            "player_id": self.player.id,
        }

        response = c.post(
            "/api/vaccination",
            data={"vaccination": json.dumps(data)},
            content_type=MULTIPART_CONTENT,
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                self.assertEqual(value, response_data[key])
        self.assertEqual(self.player.id, response_data["player"])

    def test_vaccinated(self) -> None:
        c = self.client

        certificate = SimpleUploadedFile(
            "certificate.pdf", b"file content", content_type="application/pdf"
        )
        data = {"is_vaccinated": True, "name": "CVXN", "player_id": self.player.id}
        response = c.post(
            path="/api/vaccination",
            data={"vaccination": json.dumps(data), "certificate": certificate},
            content_type=MULTIPART_CONTENT,
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                if key != "certificate":
                    self.assertEqual(value, response_data[key])
                else:
                    self.assertTrue(len(response_data[key]) > 0)
        self.assertEqual(self.player.id, response_data["player"])


class TestAccreditation(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_accreditation_not_valid(self) -> None:
        c = self.client

        certificate = SimpleUploadedFile(
            "certificate.pdf", b"file content", content_type="application/pdf"
        )
        date = str((now() - datetime.timedelta(days=18 * 31)).date())
        data = {"date": date, "level": "ADV", "player_id": self.player.id, "wfdf_id": 100}
        response = c.post(
            path="/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": certificate},
            content_type=MULTIPART_CONTENT,
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                if key != "certificate":
                    self.assertEqual(value, response_data[key])
                else:
                    self.assertTrue(len(response_data[key]) > 0)
        self.assertFalse(response_data["is_valid"])
        self.assertEqual(self.player.id, response_data["player"])

    def test_accreditation_valid(self) -> None:
        c = self.client

        certificate = SimpleUploadedFile(
            "certificate.pdf", b"file content", content_type="application/pdf"
        )
        date = str((now() - datetime.timedelta(days=18 * 30)).date())
        data = {"date": date, "level": "ADV", "player_id": self.player.id, "wfdf_id": 100}
        response = c.post(
            path="/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": certificate},
            content_type=MULTIPART_CONTENT,
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        for key, value in data.items():
            if key in response_data:
                if key != "certificate":
                    self.assertEqual(value, response_data[key])
                else:
                    self.assertTrue(len(response_data[key]) > 0)
        self.assertEqual(self.player.id, response_data["player"])
        self.assertTrue(response_data["is_valid"])

    def test_accreditation_duplicate(self) -> None:
        c = self.client

        certificate = SimpleUploadedFile(
            "certificate.pdf", b"file content", content_type="application/pdf"
        )
        date = str((now() - datetime.timedelta(days=18 * 30)).date())
        data = {"date": date, "level": "ADV", "player_id": self.player.id, "wfdf_id": 100}
        response = c.post(
            path="/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": certificate},
            content_type=MULTIPART_CONTENT,
        )
        response.json()
        self.assertEqual(200, response.status_code)

        username = email = "foo@example.com"

        user = User.objects.create(username=username, email=email)
        player = Player.objects.create(date_of_birth="2000-01-01", user=user)
        data["player_id"] = player.id
        response = c.post(
            path="/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": certificate},
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(400, response.status_code)
        self.assertIn("Wfdf id already exists", response.json()["message"])


class TestWaiver(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        season = Season.current()
        assert season is not None  # noqa: S101 - the seeded seasons cover today
        _subscription = Subscription.objects.create(
            start_date=season.start_date,
            end_date=season.end_date,
            season=season,
            player=self.player,
        )

    def test_waiver_signed(self) -> None:
        c = self.client
        response = c.post(
            "/api/waiver", data={"player_id": self.player.id}, content_type="application/json"
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        subscription = response_data["subscription"]
        self.assertEqual(self.user.get_full_name(), subscription["waiver_signed_by"])
        self.assertTrue(subscription["waiver_valid"])
        self.assertIsNotNone(subscription["waiver_signed_at"])

    def test_minor_cannot_sign_waiver(self) -> None:
        c = self.client
        self.player.date_of_birth = today() - datetime.timedelta(days=15 * 30 * 12)  # 15 years
        self.player.save()
        response = c.post(
            "/api/waiver", data={"player_id": self.player.id}, content_type="application/json"
        )
        response_data = response.json()
        self.assertEqual(400, response.status_code)
        self.assertEqual(response_data["message"], "Waiver can only signed by a guardian")
        self.player.date_of_birth = today() - datetime.timedelta(days=30 * 30 * 12)  # 30 years
        self.player.save()


class TestUPAI(ApiBaseTestCase):
    def test_get_upai_person_success(self) -> None:
        c = self.client
        c.force_login(self.user)
        player_id = self.user.player_profile.id
        player = self.user.player_profile
        player.gender = "M"
        player.match_up = "M"
        player.city = "Mysore"
        player.save()

        upai_id = 463579
        with mock.patch(
            "server.api.TopScoreClient.get_person",
            return_value={"person_id": upai_id, "api_csrf_valid": "no"},
        ):
            response = c.post(
                "/api/upai/me",
                data={"username": "foo", "password": "bar", "player_id": player_id},
                content_type="application/json",
            )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(upai_id, response_data["ultimate_central_id"])


class TestValidateTransactions(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "bank-statement.csv"
        transactions = {
            "33680091811DC": 60000,
            "326013145864": 100,
        }
        for tid, amount in transactions.items():
            ManualTransaction.objects.create(transaction_id=tid, amount=amount, user=self.user)
        self.user.is_staff = True
        self.user.save()

    def test_validate_transactions(self) -> None:
        c = self.client

        with open(self.fixture, "rb") as f:
            content = f.read()

        bank_statement = SimpleUploadedFile(
            self.fixture.name, content, content_type="application/csv"
        )
        response = c.post(
            path="/api/transactions/bulk-validate",
            data={"bank_statement": bank_statement},
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(200, response.status_code)
        stats = response.json()
        self.assertEqual(4, stats["total"])
        self.assertEqual(2, stats["invalid_found"])
        self.assertEqual(1, stats["validated"])
        self.assertEqual(1, ManualTransaction.objects.filter(validated=False).count())
        self.assertFalse(ManualTransaction.objects.get(transaction_id="33680091811DC").validated)


class TestCheckSubscriptions(ApiBaseTestCase, SubscriptionStatusTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        self.user.is_staff = True
        self.user.save()

    def test_check_subscriptions(self) -> None:
        c = self.client
        info_csv = SimpleUploadedFile(
            "info.csv",
            self.csv_data.strip().encode("utf8"),
            content_type="application/csv",
        )
        response = c.post(
            path="/api/check-subscriptions",
            data={"info_csv": info_csv},
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(len(data), len(self.csv_data.strip().split()) - 1)
        for row in data:
            self.assertIn("subscription_status", row)


class TestTournaments(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pool = create_pool("A", self.tournament, [1, 2, 3])
        start_tournament(self.tournament)

        # User who's a player in team 2, admin + coach in team 6
        self.user2 = user2 = User.objects.create(
            username="username2@foo.com", email="username2@foo.com"
        )
        user2.set_password(self.password)
        user2.save()
        person2 = UCPerson.objects.create(email="username2@foo.com", slug="username2")
        self.player2 = Player.objects.create(
            user=self.user2, date_of_birth="1990-01-01", ultimate_central_id=person2.id
        )
        UCRegistration.objects.create(
            event=self.event, team=self.teams[1], person=person2, roles=["admin", "player"]
        )
        UCRegistration.objects.create(
            event=self.event, team=self.teams[5], person=person2, roles=["admin", "coach"]
        )

        # User who's not part of any event
        self.user_with_no_event = user_with_no_event = User.objects.create(
            username="username3@foo.com", email="username3@foo.com"
        )
        user_with_no_event.set_password(self.password)
        user_with_no_event.save()
        person_with_no_event = UCPerson.objects.create(email="username3@foo.com", slug="username3")
        Player.objects.create(
            user=user_with_no_event,
            date_of_birth="1990-01-01",
            ultimate_central_id=person_with_no_event.id,
        )

        # User who's a player in team 1, and admin in team 3
        self.user_with_admin_player_roles_in_diff_teams = User.objects.create(
            username="foo@bar.com", email="foo@bar.com"
        )
        self.user_with_admin_player_roles_in_diff_teams.set_password(self.password)
        self.user_with_admin_player_roles_in_diff_teams.save()

        person_with_admin_player_roles_in_diff_teams = UCPerson.objects.create(
            email="foo@bar.com", slug="foobar"
        )
        self.player_with_admin_player_roles_in_diff_teams = Player.objects.create(
            user=self.user_with_admin_player_roles_in_diff_teams,
            ultimate_central_id=person_with_admin_player_roles_in_diff_teams.pk,
            date_of_birth="1990-01-01",
        )

        UCRegistration.objects.create(
            event=self.event,
            team=self.teams[0],
            person=person_with_admin_player_roles_in_diff_teams,
            roles=["player"],
        )

        UCRegistration.objects.create(
            event=self.event,
            team=self.teams[2],
            person=person_with_admin_player_roles_in_diff_teams,
            roles=["admin"],
        )

        # User who is admin of both team 1 and 3
        self.user_with_admin_roles_in_diff_teams = User.objects.create(
            username="foo1@bar.com", email="foo1@bar.com"
        )
        self.user_with_admin_roles_in_diff_teams.set_password(self.password)
        self.user_with_admin_roles_in_diff_teams.save()

        person_with_admin_roles_in_diff_teams = UCPerson.objects.create(
            email="foo1@bar.com", slug="foo1bar"
        )
        self.player_with_admin_roles_in_diff_teams = Player.objects.create(
            user=self.user_with_admin_roles_in_diff_teams,
            ultimate_central_id=person_with_admin_roles_in_diff_teams.pk,
            date_of_birth="1990-01-01",
        )

        UCRegistration.objects.create(
            event=self.event,
            team=self.teams[0],
            person=person_with_admin_roles_in_diff_teams,
            roles=["admin"],
        )

        UCRegistration.objects.create(
            event=self.event,
            team=self.teams[2],
            person=person_with_admin_roles_in_diff_teams,
            roles=["admin"],
        )

    def test_valid_submit_score(self) -> None:
        valid_matches = Match.objects.filter(tournament=self.tournament).filter(
            Q(team_1=self.teams[0]) | Q(team_2=self.teams[0])
        )

        self.client.force_login(self.user)
        c = self.client
        response = c.post(
            f"/api/match/{valid_matches[0].id}/submit-score",
            data={"team_1_score": 15, "team_2_score": 14},
            content_type="application/json",
        )
        match = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(15, match["suggested_score_team_1"]["score_team_1"])
        self.assertEqual(14, match["suggested_score_team_1"]["score_team_2"])
        self.assertEqual(self.player.id, match["suggested_score_team_1"]["entered_by"]["id"])

        self.client.force_login(self.user2)
        c = self.client
        response = c.post(
            f"/api/match/{valid_matches[0].id}/submit-score",
            data={"team_1_score": 15, "team_2_score": 14},
            content_type="application/json",
        )
        match = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(15, match["suggested_score_team_2"]["score_team_1"])
        self.assertEqual(14, match["suggested_score_team_2"]["score_team_2"])
        self.assertEqual(self.player2.id, match["suggested_score_team_2"]["entered_by"]["id"])

        self.assertEqual(15, match["score_team_1"])
        self.assertEqual(14, match["score_team_2"])
        self.assertEqual("COM", match["status"])

    def test_valid_submit_score_by_both_team_admin(self) -> None:
        filtered_match = (
            Match.objects.filter(tournament=self.tournament)
            .filter(team_1=self.teams[0])
            .filter(team_2=self.teams[2])[0]
        )

        self.client.force_login(self.user_with_admin_roles_in_diff_teams)
        c = self.client
        response = c.post(
            f"/api/match/{filtered_match.id}/submit-score",
            data={"team_1_score": 15, "team_2_score": 14},
            content_type="application/json",
        )
        match = response.json()

        self.assertEqual(200, response.status_code)

        self.assertEqual(15, match["suggested_score_team_1"]["score_team_1"])
        self.assertEqual(14, match["suggested_score_team_1"]["score_team_2"])
        self.assertEqual(
            self.player_with_admin_roles_in_diff_teams.id,
            match["suggested_score_team_1"]["entered_by"]["id"],
        )

        self.assertEqual(15, match["suggested_score_team_2"]["score_team_1"])
        self.assertEqual(14, match["suggested_score_team_2"]["score_team_2"])
        self.assertEqual(
            self.player_with_admin_roles_in_diff_teams.id,
            match["suggested_score_team_2"]["entered_by"]["id"],
        )

        self.assertEqual(15, match["score_team_1"])
        self.assertEqual(14, match["score_team_2"])
        self.assertEqual("COM", match["status"])

    def test_invalid_submit_score(self) -> None:
        invalid_matches = Match.objects.filter(tournament=self.tournament).filter(
            placeholder_seed_1=2, placeholder_seed_2=3
        )

        c = self.client
        response = c.post(
            f"/api/match/{invalid_matches[0].id}/submit-score",
            data={"team_1_score": 15, "team_2_score": 14},
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

    def test_user_with_team_admin_access(self) -> None:
        c = self.client
        c.force_login(self.user)
        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(self.teams[0].pk, data["playing_team_id"])
        self.assertListEqual([self.teams[0].pk], data["admin_team_ids"])
        self.assertEqual(False, data["is_staff"])
        self.assertEqual(False, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_user_with_different_team_admin_access(self) -> None:
        c = self.client
        c.force_login(self.user_with_admin_player_roles_in_diff_teams)

        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(self.teams[0].pk, data["playing_team_id"])
        self.assertListEqual([self.teams[2].pk], data["admin_team_ids"])
        self.assertEqual(False, data["is_staff"])
        self.assertEqual(False, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_player_with_multiple_teams_admin_access(self) -> None:
        c = self.client
        c.force_login(self.user2)

        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(self.teams[1].pk, data["playing_team_id"])
        self.assertListEqual([self.teams[1].pk, self.teams[5].pk], data["admin_team_ids"])
        self.assertEqual(False, data["is_staff"])
        self.assertEqual(False, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_user_without_team_admin_access(self) -> None:
        c = self.client
        c.force_login(self.user_with_no_event)

        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(0, data["playing_team_id"])
        self.assertListEqual([], data["admin_team_ids"])
        self.assertEqual(False, data["is_staff"])
        self.assertEqual(False, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_user_with_staff_access(self) -> None:
        c = self.client
        self.user.is_staff = True
        self.user.save()
        c.force_login(self.user)

        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(self.teams[0].pk, data["playing_team_id"])
        self.assertListEqual([self.teams[0].pk], data["admin_team_ids"])
        self.assertEqual(True, data["is_staff"])
        self.assertEqual(False, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_user_with_tournament_admin_access(self) -> None:
        c = self.client
        self.user.is_tournament_admin = True
        self.user.save()
        c.force_login(self.user)

        response = c.get(f"/api/me/access?tournament_slug={self.event.slug}")
        self.assertEqual(200, response.status_code)

        data = response.json()
        self.assertEqual(self.teams[0].pk, data["playing_team_id"])
        self.assertListEqual([self.teams[0].pk], data["admin_team_ids"])
        self.assertEqual(False, data["is_staff"])
        self.assertEqual(True, data["is_tournament_admin"])
        self.assertEqual(False, data["is_tournament_director"])

    def test_valid_submit_spirit_score(self) -> None:
        valid_match = (
            Match.objects.filter(tournament=self.tournament)
            .filter(team_1=self.teams[0])
            .filter(team_2=self.teams[1])[0]
        )
        valid_match.status = Match.Status.COMPLETED
        valid_match.save()

        self.client.force_login(self.user)
        c = self.client
        response = c.post(
            f"/api/match/{valid_match.id}/submit-spirit-score",
            data={
                "opponent": {
                    "rules": 2,
                    "fouls": 3,
                    "fair": 2,
                    "positive": 2,
                    "communication": 2,
                    "msp_id": self.player2.ultimate_central_id,
                    "mvp_id": self.player2.ultimate_central_id,
                },
                "self": {
                    "rules": 2,
                    "fouls": 2,
                    "fair": 2,
                    "positive": 2,
                    "communication": 2,
                    "comments": "Good game!",
                },
                "team_id": self.teams[0].id,
            },
            content_type="application/json",
        )
        match = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, match["spirit_score_team_2"]["rules"])
        self.assertEqual(3, match["spirit_score_team_2"]["fouls"])
        self.assertEqual(
            self.player2.ultimate_central_id, match["spirit_score_team_2"]["mvp"]["id"]
        )
        self.assertEqual(2, match["self_spirit_score_team_1"]["rules"])
        self.assertEqual(2, match["self_spirit_score_team_1"]["fouls"])
        self.assertEqual("Good game!", match["self_spirit_score_team_1"]["comments"])

        self.client.force_login(self.user2)
        c = self.client
        response = c.post(
            f"/api/match/{valid_match.id}/submit-spirit-score",
            data={
                "opponent": {
                    "rules": 1,
                    "fouls": 2,
                    "fair": 2,
                    "positive": 2,
                    "communication": 2,
                    "msp_id": self.player.ultimate_central_id,
                    "mvp_id": self.player.ultimate_central_id,
                },
                "self": {"rules": 3, "fouls": 2, "fair": 2, "positive": 2, "communication": 2},
                "team_id": self.teams[1].id,
            },
            content_type="application/json",
        )
        match = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, match["spirit_score_team_1"]["rules"])
        self.assertEqual(2, match["spirit_score_team_1"]["fouls"])
        self.assertEqual(self.player.ultimate_central_id, match["spirit_score_team_1"]["mvp"]["id"])
        self.assertEqual(3, match["self_spirit_score_team_2"]["rules"])
        self.assertEqual(2, match["self_spirit_score_team_2"]["fouls"])

        # Level teams are separated by final placement, so ranks are sequential.
        expected_tournament_spirit_ranking = [
            {"team_id": 2, "points": 11.0, "self_points": 11.0, "rank": 1},
            {"team_id": 1, "points": 9.0, "self_points": 10.0, "rank": 2},
            {"team_id": 3, "points": 0.0, "self_points": 0.0, "rank": 3},
            {"team_id": 4, "points": 0.0, "self_points": 0.0, "rank": 4},
            {"team_id": 5, "points": 0.0, "self_points": 0.0, "rank": 5},
            {"team_id": 6, "points": 0.0, "self_points": 0.0, "rank": 6},
            {"team_id": 7, "points": 0.0, "self_points": 0.0, "rank": 7},
            {"team_id": 8, "points": 0.0, "self_points": 0.0, "rank": 8},
        ]

        self.tournament.refresh_from_db()
        self.assertEqual(expected_tournament_spirit_ranking, self.tournament.spirit_ranking)

    def test_invalid_submit_spirit_score(self) -> None:
        invalid_matches = Match.objects.filter(tournament=self.tournament).filter(
            placeholder_seed_1=2, placeholder_seed_2=3
        )

        self.client.force_login(self.user)
        c = self.client
        response = c.post(
            f"/api/match/{invalid_matches[0].id}/submit-spirit-score",
            data={
                "opponent": {
                    "rules": 1,
                    "fouls": 2,
                    "fair": 2,
                    "positive": 2,
                    "communication": 2,
                    "msp_id": self.player.ultimate_central_id,
                    "mvp_id": self.player.ultimate_central_id,
                },
                "self": {"rules": 3, "fouls": 2, "fair": 2, "positive": 2, "communication": 2},
                "team_id": self.teams[0].id,
            },
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

        response = c.post(
            f"/api/match/{invalid_matches[0].id}/submit-spirit-score",
            data={
                "opponent": {
                    "rules": 1,
                    "fouls": 2,
                    "fair": 2,
                    "positive": 2,
                    "communication": 2,
                    "msp_id": self.player.ultimate_central_id,
                    "mvp_id": self.player.ultimate_central_id,
                },
                "self": {"rules": 3, "fouls": 2, "fair": 2, "positive": 2, "communication": 2},
                "team_id": self.teams[1].id,
            },
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

    def test_delete_match(self) -> None:
        match = Match.objects.filter()[0]

        c = self.client
        self.user.is_staff = True
        self.user.save()
        c.force_login(self.user)

        response = c.delete(
            f"/api/match/{match.id}",
        )
        self.assertEqual(200, response.status_code)
        with self.assertRaises(Match.DoesNotExist):
            Match.objects.get(id=match.id)


class TestContactForm(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_contact_form_valid(self) -> None:
        c = self.client

        attachment_name = "certificate.pdf"
        path = f"contact-form-attachments/{attachment_name}"
        default_storage.delete(path)  # type: ignore[attr-defined]
        attachment = SimpleUploadedFile(
            attachment_name, b"file content", content_type="application/pdf"
        )
        data = {
            "subject": "Payment Gateway",
            "description": "I can't record a payment",
        }
        response = c.post(
            path="/api/contact",
            data={"contact_form": json.dumps(data), "attachment": attachment},
            content_type=MULTIPART_CONTENT,
        )
        response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(mail.outbox))
        email = mail.outbox[0]
        self.assertEqual(data["subject"], email.subject)
        self.assertIn(self.user.email, str(email.message()))
        self.assertTrue(default_storage.exists(path))  # type: ignore[attr-defined]
        self.assertIn(path, str(email.message()))
