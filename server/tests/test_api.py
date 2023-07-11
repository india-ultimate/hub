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
