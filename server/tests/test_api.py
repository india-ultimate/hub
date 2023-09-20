import datetime
import json
import uuid
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test.client import MULTIPART_CONTENT
from django.utils.timezone import now

from server.constants import (
    ANNUAL_MEMBERSHIP_AMOUNT,
    EVENT_MEMBERSHIP_AMOUNT,
    SPONSORED_ANNUAL_MEMBERSHIP_AMOUNT,
)
from server.models import (
    Event,
    Guardianship,
    ManualTransaction,
    Membership,
    Player,
    RazorpayTransaction,
    User,
)
from server.tests.base import ApiBaseTestCase, fake_id, fake_order


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

    def test_firebase_login_failure(self) -> None:
        c = Client()
        with mock.patch("firebase_admin.auth.get_user", return_value=None):
            response = c.post(
                "/api/firebase-login",
                data={"token": "token", "uid": "fake-uid", "login": True},
                content_type="application/json",
            )
        self.assertEqual(403, response.status_code)

    def test_firebase_login(self) -> None:
        c = Client()
        token = "token"
        uid = "uid"
        with mock.patch(
            "firebase_admin.auth.get_user",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/firebase-login",
                data={"token": token, "uid": uid, "login": True},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(self.username, data["username"])
        self.assertIn("firebase_token", c.session.keys())
        self.assertEqual(token, c.session["firebase_token"])

    def test_firebase_signup(self) -> None:
        c = Client()
        token = "my-secret-token"
        email = "blah@example.com"
        with mock.patch("firebase_admin.auth.get_user"):
            response = c.post(
                "/api/firebase-login",
                data={
                    "token": token,
                    "uid": "fake-uid",
                    "email": email,
                    "first_name": "John",
                    "last_name": "Doe",
                    "sign_up": True,
                    "phone": "+919999900000",
                },
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(email, data["username"])
        self.assertIn("firebase_token", c.session.keys())
        self.assertEqual(token, c.session["firebase_token"])

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

        # Firebase login and logout
        with mock.patch(
            "firebase_admin.auth.get_user",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/firebase-login",
                data={"token": "token", "uid": "uid", "login": True},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        response.json()
        self.assertIn("firebase_token", c.session.keys())

        response = c.post("/api/logout", content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertNotIn("firebase_token", c.session.keys())


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
            "gender": "F",
            "city": "Bangalore",
            "first_name": "Nora",
            "last_name": "Quinn",
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

    def test_edit_registration(self) -> None:
        c = self.client

        self.assertEqual("", self.player.user.phone)
        self.assertEqual("", self.player.user.first_name)
        self.assertEqual("", self.player.city)

        data = {
            "player_id": self.player.id,
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
            "gender": "F",
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

    def test_register_others(self) -> None:
        c = self.client
        self.user.player_profile.delete()
        data = {
            "email": "foo@email.com",
            "phone": "+1234567890",
            "date_of_birth": "1990-01-01",
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
        self.assertEqual("usxxxxme@foo.com", user_data["email"])
        self.assertNotIn("membership", user_data)
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
        self.assertIn("membership", user_data)
        self.assertIn("guardian", user_data)

        response = c.get("/api/players", content_type="application/json")
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        user_data = data[0]
        self.assertIn("city", user_data)
        self.assertIn("state_ut", user_data)
        self.assertEqual("usxxxxme@foo.com", user_data["email"])
        self.assertNotIn("membership", user_data)
        self.assertNotIn("guardian", user_data)


class TestPayment(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def test_create_order_no_player(self) -> None:
        c = self.client

        player_id = 200

        # Player does not exist
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player_id,
                    "year": 2023,
                },
                content_type="application/json",
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Player does not exist!", response.json()["message"])

    def test_create_manual_transaction_player_exists(self) -> None:
        c = self.client
        player = self.player
        amount = ANNUAL_MEMBERSHIP_AMOUNT
        transaction_id = "123123123"
        response = c.post(
            f"/api/manual-transaction/{transaction_id}",
            data={
                "player_id": player.id,
                "year": 2023,
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("transaction_id", order_data)
        transaction_id = order_data["transaction_id"]
        transaction = ManualTransaction.objects.get(transaction_id=transaction_id)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())
        self.assertFalse(transaction.validated)
        self.assertEqual("2023-06-01", player.membership.start_date.strftime("%Y-%m-%d"))
        self.assertEqual("2024-05-31", player.membership.end_date.strftime("%Y-%m-%d"))

    def test_create_manual_transaction_membership_exists(self) -> None:
        c = self.client
        player = self.player
        membership = Membership.objects.create(
            player=player, start_date="2022-01-01", end_date="2022-12-31"
        )
        amount = ANNUAL_MEMBERSHIP_AMOUNT
        transaction_id = "123123123"
        response = c.post(
            f"/api/manual-transaction/{transaction_id}",
            data={
                "player_id": player.id,
                "year": 2023,
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("transaction_id", order_data)
        transaction_id = order_data["transaction_id"]
        transaction = ManualTransaction.objects.get(transaction_id=transaction_id)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())
        self.assertFalse(transaction.validated)
        membership.refresh_from_db()
        self.assertEqual("2023-06-01", membership.start_date.strftime("%Y-%m-%d"))
        self.assertEqual("2024-05-31", membership.end_date.strftime("%Y-%m-%d"))

    def test_create_order_player_exists(self) -> None:
        c = self.client
        player = self.player
        amount = ANNUAL_MEMBERSHIP_AMOUNT
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(amount),
        ) as f:
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player.id,
                    "year": 2023,
                },
                content_type="application/json",
            )
        f.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("order_id", order_data)
        order_id = order_data["order_id"]
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.PENDING,
            transaction.status,
        )
        self.assertEqual("2023-06-01", transaction.start_date.strftime("%Y-%m-%d"))
        self.assertEqual("2024-05-31", transaction.end_date.strftime("%Y-%m-%d"))

    def test_create_order_sponsored_player_exists(self) -> None:
        c = self.client
        player = self.player
        player.sponsored = True
        player.save()
        amount = SPONSORED_ANNUAL_MEMBERSHIP_AMOUNT
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(amount),
        ) as f:
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player.id,
                    "year": 2023,
                },
                content_type="application/json",
            )
        f.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("order_id", order_data)
        order_id = order_data["order_id"]
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(amount, transaction.amount)
        self.assertIn(player, transaction.players.all())
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.PENDING,
            transaction.status,
        )
        self.assertEqual("2023-06-01", transaction.start_date.strftime("%Y-%m-%d"))
        self.assertEqual("2024-05-31", transaction.end_date.strftime("%Y-%m-%d"))

    def test_create_order_event_membership_no_player(self) -> None:
        c = self.client

        player_id = 200
        event_id = 20

        # Player does not exist
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player_id,
                    "event_id": event_id,
                },
                content_type="application/json",
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Player does not exist!", response.json()["message"])

    def test_create_order_event_membership_no_event(self) -> None:
        c = self.client
        event_id = 20

        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(0),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": self.player.id,
                    "event_id": event_id,
                },
                content_type="application/json",
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Event does not exist!", response.json()["message"])

    def test_create_order_event_membership(self) -> None:
        c = self.client
        # Player exists, event exists, membership does not exist
        player = self.player
        event = Event.objects.create(
            start_date="2023-09-08", end_date="2023-09-10", title="South Regionals"
        )
        event.refresh_from_db()
        amount = EVENT_MEMBERSHIP_AMOUNT

        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(amount),
        ) as f:
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player.id,
                    "event_id": event.id,
                },
                content_type="application/json",
            )
        f.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("order_id", order_data)
        order_id = order_data["order_id"]
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(self.user, transaction.user)
        self.assertIn(player, transaction.players.all())
        self.assertEqual(player.membership.start_date, event.start_date)
        self.assertEqual(player.membership.end_date, event.end_date)
        self.assertFalse(player.membership.is_annual)
        self.assertEqual(player.membership.event, event)
        self.assertEqual(transaction.event, event)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.PENDING,
            transaction.status,
        )
        self.assertEqual(event.start_date, transaction.start_date)
        self.assertEqual(event.end_date, transaction.end_date)

    def test_create_manual_transaction_event_membership(self) -> None:
        c = self.client
        # Player exists, event exists, membership does not exist
        player = self.player
        event = Event.objects.create(
            start_date="2023-09-08", end_date="2023-09-10", title="South Regionals"
        )
        event.refresh_from_db()
        transaction_id = "1231231234"

        response = c.post(
            f"/api/manual-transaction/{transaction_id}",
            data={
                "player_id": player.id,
                "event_id": event.id,
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("transaction_id", order_data)
        transaction_id = order_data["transaction_id"]
        transaction = ManualTransaction.objects.get(transaction_id=transaction_id)
        self.assertEqual(self.user, transaction.user)
        self.assertIn(player, transaction.players.all())
        self.assertEqual(player.membership.start_date, event.start_date)
        self.assertEqual(player.membership.end_date, event.end_date)
        self.assertFalse(player.membership.is_annual)
        self.assertEqual(player.membership.event, event)
        self.assertEqual(transaction.event, event)
        self.assertFalse(transaction.validated)

    def test_create_order_group_membership_missing_players(self) -> None:
        c = self.client

        player_ids = [200, 220, 230, 225]

        # Player does not exist
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "player_ids": player_ids,
                    "year": 2023,
                },
                content_type="application/json",
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Some players couldn't be found in the DB: [200, 220, 225, 230]",
            response.json()["message"],
        )

    def test_create_order_group_membership(self) -> None:
        c = self.client
        player_ids = [200, 220, 230, 225]

        for id_ in player_ids:
            username = str(uuid.uuid4())[:8]
            user = User.objects.create(username=username)
            date_of_birth = "2001-01-01"
            player = Player.objects.create(id=id_, user=user, date_of_birth=date_of_birth)

        amount = ANNUAL_MEMBERSHIP_AMOUNT * len(player_ids)
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(amount),
        ) as f:
            response = c.post(
                "/api/create-order",
                data={
                    "player_ids": player_ids,
                    "year": 2023,
                },
                content_type="application/json",
            )
        f.assert_called_once_with(amount, receipt=mock.ANY, notes=mock.ANY)
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("order_id", order_data)
        order_id = order_data["order_id"]
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(self.user, transaction.user)
        self.assertIsNotNone(transaction.start_date)
        self.assertIsNotNone(transaction.end_date)
        for player_id in player_ids:
            player = Player.objects.get(id=player_id)
            self.assertIn(player, transaction.players.all())
            self.assertEqual(player.membership.start_date, transaction.start_date)
            self.assertEqual(player.membership.end_date, transaction.end_date)
            self.assertTrue(player.membership.is_annual)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.PENDING,
            transaction.status,
        )

    def test_create_manual_transaction_group_membership(self) -> None:
        c = self.client
        player_ids = [200, 220, 230, 225]

        for id_ in player_ids:
            username = str(uuid.uuid4())[:8]
            user = User.objects.create(username=username)
            date_of_birth = "2001-01-01"
            player = Player.objects.create(id=id_, user=user, date_of_birth=date_of_birth)

        ANNUAL_MEMBERSHIP_AMOUNT * len(player_ids)
        transaction_id = "432198765"
        response = c.post(
            f"/api/manual-transaction/{transaction_id}",
            data={
                "player_ids": player_ids,
                "year": 2023,
            },
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertIn("amount", order_data)
        self.assertIn("transaction_id", order_data)
        transaction_id = order_data["transaction_id"]
        transaction = ManualTransaction.objects.get(transaction_id=transaction_id)
        self.assertEqual(self.user, transaction.user)
        for player_id in player_ids:
            player = Player.objects.get(id=player_id)
            self.assertIn(player, transaction.players.all())
            self.assertTrue(player.membership.is_annual)
        self.assertFalse(transaction.validated)

    def test_payment_success(self) -> None:
        c = self.client
        amount = 60000
        order = fake_order(amount)
        order_id = order["order_id"]
        user = self.user
        start_date = "2023-06-01"
        end_date = "2024-05-31"
        player = self.player
        membership = Membership.objects.create(
            start_date=start_date, end_date=end_date, player=player
        )
        order.update(
            {"start_date": start_date, "end_date": end_date, "user": user, "players": [player]}
        )
        transaction = RazorpayTransaction.create_from_order_data(order)
        self.assertFalse(membership.is_active)
        self.assertEqual(self.user, transaction.user)
        self.assertIn(player, transaction.players.all())

        payment_id = f"pay_{fake_id(16)}"
        signature = f"{fake_id(64)}"
        with mock.patch("server.api.verify_razorpay_payment", return_value=True):
            response = c.post(
                "/api/payment-success",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                },
                content_type="application/json",
            )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        player_data = data[0]
        self.assertEqual(player.id, player_data["id"])
        self.assertEqual(
            membership.membership_number, player_data["membership"]["membership_number"]
        )

        transaction.refresh_from_db()
        self.assertEqual(transaction.payment_id, payment_id)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )

        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
        self.assertEqual(start_date, membership.start_date.strftime("%Y-%m-%d"))
        self.assertEqual(end_date, membership.end_date.strftime("%Y-%m-%d"))

    def test_payment_success_group_membership(self) -> None:
        c = self.client
        n_players = 4
        amount = 60000 * n_players
        order = fake_order(amount)
        order_id = order["order_id"]
        user = self.user
        start_date = "2023-06-01"
        end_date = "2024-05-31"

        players = []
        for _ in range(n_players):
            username = str(uuid.uuid4())[:8]
            user_ = User.objects.create(username=username)
            date_of_birth = "2001-01-01"
            player = Player.objects.create(user=user_, date_of_birth=date_of_birth)
            players.append(player)

        order.update(
            {"start_date": start_date, "end_date": end_date, "user": user, "players": players}
        )
        transaction = RazorpayTransaction.create_from_order_data(order)
        self.assertEqual(self.user, transaction.user)
        for player in players:
            self.assertIn(player, transaction.players.all())

        payment_id = f"pay_{fake_id(16)}"
        signature = f"{fake_id(64)}"
        with mock.patch("server.api.verify_razorpay_payment", return_value=True):
            response = c.post(
                "/api/payment-success",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                },
                content_type="application/json",
            )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(n_players, len(data))
        for player_data in data:
            membership = player_data["membership"]
            self.assertTrue(membership["is_active"])
            self.assertEqual(start_date, membership["start_date"])
            self.assertEqual(end_date, membership["end_date"])

        transaction.refresh_from_db()
        self.assertEqual(transaction.payment_id, payment_id)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )

    def test_payment_success_event_membership(self) -> None:
        c = self.client
        amount = EVENT_MEMBERSHIP_AMOUNT
        order = fake_order(amount)
        order_id = order["order_id"]
        user = self.user
        start_old = "2022-06-01"
        end_old = "2023-05-31"
        start_date = "2023-06-01"
        end_date = "2024-05-31"
        player = self.player
        event_old = Event.objects.create(start_date=start_old, end_date=end_old, title="Old")
        event = Event.objects.create(start_date=start_date, end_date=end_date, title="New")
        event.refresh_from_db()
        membership = Membership.objects.create(
            start_date=start_old, end_date=end_old, player=player, event=event_old
        )
        order.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "user": user,
                "players": [player],
                "event": event,
            }
        )
        transaction = RazorpayTransaction.create_from_order_data(order)
        self.assertFalse(membership.is_active)
        self.assertEqual(self.user, transaction.user)
        self.assertIn(player, transaction.players.all())
        self.assertEqual(event_old, player.membership.event)
        self.assertEqual(event, transaction.event)

        payment_id = f"pay_{fake_id(16)}"
        signature = f"{fake_id(64)}"
        with mock.patch("server.api.verify_razorpay_payment", return_value=True):
            response = c.post(
                "/api/payment-success",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                },
                content_type="application/json",
            )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        player_data = data[0]
        self.assertEqual(player.id, player_data["id"])
        self.assertEqual(
            membership.membership_number, player_data["membership"]["membership_number"]
        )

        transaction.refresh_from_db()
        self.assertEqual(transaction.payment_id, payment_id)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )
        self.assertEqual(event, transaction.event)

        membership.refresh_from_db()
        self.assertTrue(membership.is_active)
        self.assertEqual(event.start_date, membership.start_date)
        self.assertEqual(event.end_date, membership.end_date)
        self.assertEqual(event, membership.event)

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
        order = fake_order(ANNUAL_MEMBERSHIP_AMOUNT * 2)
        order.update(user=self.user, players=players[2:], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction for current user's player
        order = fake_order(ANNUAL_MEMBERSHIP_AMOUNT)
        order.update(user=users[0], players=players[:1], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction for current user's ward
        order = fake_order(ANNUAL_MEMBERSHIP_AMOUNT)
        order.update(user=users[2], players=players[1:2], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)
        orders.add(order["order_id"])

        # Create transaction made by another user
        order = fake_order(ANNUAL_MEMBERSHIP_AMOUNT * 2)
        order.update(user=users[2], players=players[2:], transaction_id=order["order_id"])
        ManualTransaction.create_from_order_data(order)

        response = c.get(
            "/api/transactions",
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code)
        response_data = response.json()

        self.assertEqual(len(orders), len(response_data))
        self.assertEqual(orders, {t["transaction_id"] for t in response_data})

    def test_razorpay_failures(self) -> None:
        player = self.player
        c = self.client
        with mock.patch("server.api.create_razorpay_order", return_value=None):
            response = c.post(
                "/api/create-order",
                data={
                    "player_id": player.id,
                    "year": 2023,
                },
                content_type="application/json",
            )

        self.assertEqual(502, response.status_code)
        self.assertIn(b"Razorpay", response.content)


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


class TestWaiver(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)
        start_date = "2023-06-01"
        end_date = "2024-05-31"
        _membership = Membership.objects.create(
            start_date=start_date, end_date=end_date, player=self.player
        )

    def test_waiver_signed(self) -> None:
        c = self.client
        response = c.post(
            "/api/waiver", data={"player_id": self.player.id}, content_type="application/json"
        )
        response_data = response.json()
        self.assertEqual(200, response.status_code)
        membership = response_data["membership"]
        self.assertEqual(self.user.get_full_name(), membership["waiver_signed_by"])
        self.assertTrue(membership["waiver_valid"])
        self.assertIsNotNone(membership["waiver_signed_at"])

    def test_minor_cannot_sign_waiver(self) -> None:
        c = self.client
        Guardianship.objects.create(
            user=self.user, player=self.player, relation=Guardianship.Relation.MO
        )
        response = c.post(
            "/api/waiver", data={"player_id": self.player.id}, content_type="application/json"
        )
        response_data = response.json()
        self.assertEqual(400, response.status_code)
        self.assertEqual(response_data["message"], "Waiver can only signed by a guardian")


class TestUPAI(ApiBaseTestCase):
    def test_get_upai_person_success(self) -> None:
        c = self.client
        c.force_login(self.user)
        player_id = self.user.player_profile.id
        player = self.user.player_profile
        player.gender = "M"
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

    def test_validate_transactions(self) -> None:
        c = self.client

        with open(self.fixture, "rb") as f:
            content = f.read()

        bank_statement = SimpleUploadedFile(
            self.fixture.name, content, content_type="application/csv"
        )
        response = c.post(
            path="/api/validate-transactions",
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
