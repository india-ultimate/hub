# ruff: noqa: S106
import datetime

from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils.timezone import now
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken

from server.core.models import User
from server.mcp.auth import TokenInfo, authenticate
from server.tests.test_mcp_auth import make_token

URL = "/api/me/connected-apps"


class TestConnectedApps(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="a@x.com", email="a@x.com")
        self.other = User.objects.create(username="b@x.com", email="b@x.com")
        self.client.force_login(self.user)

    def connect(self, user: User, bearer: str, scope: str = "hub:read") -> AccessToken:
        return make_token(user, bearer=bearer, scope=scope)

    def bearer(self, token: str) -> TokenInfo | None:
        return authenticate(RequestFactory().post("/mcp", HTTP_AUTHORIZATION=f"Bearer {token}"))

    def test_lists_only_own_apps_in_plain_words(self) -> None:
        mine = self.connect(self.user, "mine", "hub:read hub:write")
        self.connect(self.other, "theirs")

        data = self.client.get(URL).json()

        self.assertEqual([a["application_id"] for a in data], [mine.application_id])
        self.assertEqual(data[0]["name"], "Claude")
        self.assertEqual(data[0]["scopes"], ["See your Hub data", "Make changes in Hub as you"])
        self.assertTrue(data[0]["connected_at"])

    def test_expired_token_without_refresh_is_not_listed(self) -> None:
        token = self.connect(self.user, "old")
        token.expires = now() - datetime.timedelta(hours=1)
        token.save()
        self.assertEqual(self.client.get(URL).json(), [])

    def test_expired_access_with_live_refresh_is_listed(self) -> None:
        token = self.connect(self.user, "old")
        token.expires = now() - datetime.timedelta(hours=1)
        token.save()
        RefreshToken.objects.create(
            user=self.user, application=token.application, token="r", access_token=token
        )
        self.assertEqual(len(self.client.get(URL).json()), 1)

    def test_app_with_only_a_refresh_token_is_listed(self) -> None:
        token = self.connect(self.user, "old")
        refresh = RefreshToken.objects.create(
            user=self.user, application=token.application, token="r", access_token=token
        )
        token.delete()
        refresh.refresh_from_db()

        data = self.client.get(URL).json()

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["scopes"], [])
        self.assertTrue(data[0]["connected_at"])

    def test_revoke_deletes_only_callers_tokens_for_that_app(self) -> None:
        mine = self.connect(self.user, "mine")
        RefreshToken.objects.create(
            user=self.user, application=mine.application, token="r", access_token=mine
        )
        Grant.objects.create(
            user=self.user,
            application=mine.application,
            code="g",
            expires=now() + datetime.timedelta(minutes=1),
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
        )
        kept = self.connect(self.user, "kept")
        AccessToken.objects.create(
            user=self.other,
            application=mine.application,
            token="theirs-same-app",
            scope="hub:read",
            expires=now() + datetime.timedelta(hours=1),
        )

        response = self.client.delete(f"{URL}/{mine.application_id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccessToken.objects.filter(token="mine").exists())
        self.assertFalse(RefreshToken.objects.filter(user=self.user, token="r").exists())
        self.assertFalse(Grant.objects.filter(user=self.user).exists())
        self.assertTrue(AccessToken.objects.filter(token="kept").exists())
        self.assertTrue(AccessToken.objects.filter(token="theirs-same-app").exists())
        self.assertEqual(AccessToken.objects.get(token="kept").application_id, kept.application_id)
        self.assertTrue(Application.objects.filter(pk=mine.application_id).exists())

    def test_other_oauth_apps_are_neither_listed_nor_revoked(self) -> None:
        token = self.connect(self.user, "elsewhere")
        Application.objects.filter(pk=token.application_id).update(
            redirect_uris="https://other.example/callback"
        )

        self.assertEqual([], self.client.get(URL).json())
        self.assertEqual(404, self.client.delete(f"{URL}/{token.application_id}").status_code)
        self.assertTrue(AccessToken.objects.filter(token="elsewhere").exists())

    def test_loopback_clients_count_as_connected_apps(self) -> None:
        token = self.connect(self.user, "local")
        Application.objects.filter(pk=token.application_id).update(
            redirect_uris="http://localhost:8123/cb http://127.0.0.1:8123/cb"
        )

        self.assertEqual(1, len(self.client.get(URL).json()))

    def test_revoke_unknown_or_not_connected_app_is_404(self) -> None:
        theirs = self.connect(self.other, "theirs")
        self.assertEqual(self.client.delete(f"{URL}/{theirs.application_id}").status_code, 404)
        self.assertTrue(AccessToken.objects.filter(token="theirs").exists())

    def test_bearer_stops_working_after_revoke(self) -> None:
        token = self.connect(self.user, "bearer")
        self.assertIsNotNone(self.bearer("bearer"))
        self.client.delete(f"{URL}/{token.application_id}")
        self.assertIsNone(self.bearer("bearer"))

    def test_revoke_without_csrf_token_is_rejected(self) -> None:
        token = self.connect(self.user, "mine")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.delete(f"{URL}/{token.application_id}")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(AccessToken.objects.filter(token="mine").exists())

    def test_requires_login(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_disabled_returns_404(self) -> None:
        token = self.connect(self.user, "mine")
        with override_settings(MCP_ENABLED=False):
            self.assertEqual(self.client.get(URL).status_code, 404)
            self.assertEqual(self.client.delete(f"{URL}/{token.application_id}").status_code, 404)
        self.assertTrue(AccessToken.objects.filter(token="mine").exists())
