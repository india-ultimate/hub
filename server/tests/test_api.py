import datetime
import random
import string
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from requests.exceptions import RequestException
from server.models import Membership, Player, RazorpayTransaction

User = get_user_model()


def fake_id(n):
    choices = string.digits + string.ascii_letters
    return "".join(random.choice(choices) for _ in range(n))


def fake_order(amount):
    order_id = f"order_{fake_id(16)}"
    return {
        "order_id": order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": "78e1cdbe:2023-06-01:1689402191",
        "key": "rzp_test_2wH8PYPLML64BA",
        "name": "UPAI Hub",
        "image": "https://d36m266ykvepgv.cloudfront.net/uploads/media/o4G97mT9vR/s-448-250/upai-2.png",
        "description": "Membership for ",
        "prefill": {"name": "", "email": "username@foo.com", "contact": ""},
    }


def create_player(user):
    return Player.objects.create(user=user, date_of_birth=datetime.date.today())


class TestLogin(TestCase):
    def setUp(self):
        super().setUp()
        self.username = "username@foo.com"
        self.password = "password"
        user = User.objects.create(username=self.username, email=self.username)
        user.set_password(self.password)
        user.save()

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
        response = c.post(
            "/api/firebase-login",
            data={"token": "token", "uid": "fake-uid"},
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
                data={"token": token, "uid": uid},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(self.username, data["username"])
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
                data={"token": "token", "uid": "uid"},
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIn("firebase_token", c.session.keys())

        response = c.post("/api/logout", content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertNotIn("firebase_token", c.session.keys())


class TestPayment(TestCase):
    def setUp(self):
        super().setUp()

        self.client = Client()
        self.username = "username@foo.com"
        self.user = User.objects.create(username=self.username, email=self.username)
        self.client.force_login(self.user)

    def test_create_order(self):
        c = self.client

        amount = 60000
        player_id = 200
        start_date = "2023-06-01"
        end_date = "2024-05-31"

        # Player does not exist
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=mock.MagicMock(email=self.username),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "type": "membership",
                    "amount": amount,
                    "player_id": player_id,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                content_type="application/json",
            )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Player does not exist!", response.json()["message"])

        # Player exists, membership does not exist
        player = create_player(user=self.user)
        with mock.patch(
            "server.api.create_razorpay_order",
            return_value=fake_order(amount),
        ):
            response = c.post(
                "/api/create-order",
                data={
                    "type": "membership",
                    "amount": amount,
                    "player_id": player.id,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                content_type="application/json",
            )
        self.assertEqual(200, response.status_code)
        order_data = response.json()
        self.assertEqual(amount, order_data["amount"])
        self.assertIn("order_id", order_data)
        order_id = order_data["order_id"]
        transaction = RazorpayTransaction.objects.get(order_id=order_id)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(player.membership, transaction.membership)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.PENDING,
            transaction.status,
        )

    def test_payment_success(self):
        c = self.client
        amount = 60000
        order = fake_order(amount)
        order_id = order["order_id"]
        user = self.user
        start_date = "2023-06-01"
        end_date = "2024-05-31"
        player = create_player(user=user)
        membership = Membership.objects.create(
            start_date=start_date, end_date=end_date, player=player
        )
        transaction = RazorpayTransaction.create_from_order_data(
            order, user=user, membership=membership
        )
        self.assertFalse(membership.is_active)
        self.assertEqual(self.user, transaction.user)
        self.assertEqual(player.membership, transaction.membership)

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
        self.assertEqual(player.id, data["id"])
        self.assertEqual(membership.membership_number, data["membership"]["membership_number"])

        transaction.refresh_from_db()
        self.assertEqual(transaction.payment_id, payment_id)
        self.assertEqual(
            RazorpayTransaction.TransactionStatusChoices.COMPLETED,
            transaction.status,
        )

        membership.refresh_from_db()
        self.assertTrue(membership.is_active)

    def test_razorpay_failures(self):
        player = create_player(user=self.user)
        c = self.client
        with mock.patch("server.api.create_razorpay_order", side_effect=RequestException) as e:
            response = c.post(
                "/api/create-order",
                data={
                    "type": "membership",
                    "amount": 10000,
                    "player_id": player.id,
                    "start_date": "2024-05-31",
                    "end_date": "2023-06-01",
                },
                content_type="application/json",
            )

        self.assertEqual(502, response.status_code)
        self.assertIn(b"Razorpay", response.content)
