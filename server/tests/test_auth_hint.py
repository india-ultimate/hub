from django.contrib.auth import get_user_model
from django.test import TestCase

from server.middleware import AUTH_HINT_COOKIE

from .test_config import TEST_PASSWORD


class AuthHintCookieTest(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="hint@example.com", email="hint@example.com", password=TEST_PASSWORD
        )

    def test_anonymous_request_sets_no_hint(self) -> None:
        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn(AUTH_HINT_COOKIE, response.cookies)

    def test_authenticated_request_sets_readable_hint(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, 200)
        cookie = response.cookies[AUTH_HINT_COOKIE]
        self.assertEqual(cookie.value, "1")
        self.assertFalse(cookie["httponly"])

    def test_hint_is_refreshed_while_signed_in(self) -> None:
        self.client.force_login(self.user)
        self.client.get("/api/me")

        response = self.client.get("/api/me")

        self.assertEqual(response.cookies[AUTH_HINT_COOKIE].value, "1")

    def test_logout_clears_the_hint(self) -> None:
        self.client.force_login(self.user)
        self.client.get("/api/me")
        self.assertEqual(self.client.cookies[AUTH_HINT_COOKIE].value, "1")

        response = self.client.post("/api/logout")

        self.assertEqual(response.cookies[AUTH_HINT_COOKIE].value, "")
