from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()


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
