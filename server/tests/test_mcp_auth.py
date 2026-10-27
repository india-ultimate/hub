import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from unittest import mock
from urllib.parse import parse_qs, quote, urlparse

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.utils.timezone import now
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher
from oauth2_provider.models import AccessToken, Application
from oauth2_provider.settings import oauth2_settings
from redis.exceptions import TimeoutError as RedisTimeoutError

from server.cache import store
from server.core.models import User
from server.duplicates.players.merge import merge_accounts
from server.mcp.auth import TokenInfo, authenticate
from server.mcp.redirects import PolicyMetadataFetcher
from server.tests.test_merge import MergeTestCase

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

WELL_KNOWN = [
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/.well-known/oauth-authorization-server",
]


def make_token(
    user: User,
    bearer: str = "tok",
    scope: str = "hub:read",
    resource: list[str] | None = None,
    expires: datetime.datetime | None = None,
) -> AccessToken:
    application = Application.objects.create(
        name="Claude",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/api/mcp/auth_callback",
        user=user,
    )
    return AccessToken.objects.create(
        user=user,
        application=application,
        token=bearer,
        scope=scope,
        expires=expires or now() + datetime.timedelta(hours=1),
        resource=[settings.MCP_RESOURCE_URL] if resource is None else resource,
    )


JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
# As Claude and ChatGPT published them (October 2026).
CLAUDE_DOCUMENT: dict[str, Any] = {
    "client_id": "https://claude.ai/oauth/mcp-oauth-client-metadata",
    "client_name": "Claude",
    "client_uri": "https://claude.ai",
    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
    "grant_types": [
        "authorization_code",
        "refresh_token",
        JWT_BEARER,
    ],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
CHATGPT_DOCUMENT: dict[str, Any] = {
    "client_id": "https://chatgpt.com/oauth/client.json",
    "client_name": "ChatGPT",
    "client_uri": "https://chatgpt.com/",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "token_endpoint_auth_method": "private_key_jwt",
    "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "logo_uri": "https://persistent.oaistatic.com/sonic/misc/openai-logo.png",
    "token_endpoint_auth_signing_alg": "RS256",
    "jwks_uri": "https://chatgpt.com/oauth/jwks.json",
}


class McpAuthTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="a@x.com", email="a@x.com")

    def authenticate(self, bearer: str = "tok") -> TokenInfo | None:
        request = RequestFactory().post("/mcp", HTTP_AUTHORIZATION=f"Bearer {bearer}")
        return authenticate(request)


class TestBearerAuth(McpAuthTestCase):
    def test_no_token_gets_401_with_resource_metadata(self) -> None:
        response = self.client.post("/mcp")

        self.assertEqual(response.status_code, 401)
        challenge = response["WWW-Authenticate"]
        self.assertIn(
            f'resource_metadata="{settings.PUBLIC_URL}'
            '/.well-known/oauth-protected-resource/mcp"',
            challenge,
        )
        self.assertIn('scope="hub:read hub:write"', challenge)

    def test_no_token_challenge_has_no_error(self) -> None:
        self.assertNotIn("error=", self.client.post("/mcp")["WWW-Authenticate"])

    def test_invalid_or_expired_token_says_invalid_token_and_is_logged(self) -> None:
        make_token(self.user, "old", expires=now() - datetime.timedelta(seconds=1))
        for bearer in ("nope", "old"):
            with self.subTest(bearer=bearer), self.assertLogs("server.mcp", "WARNING") as logs:
                response = self.client.post("/mcp", headers={"Authorization": f"Bearer {bearer}"})

                self.assertEqual(response.status_code, 401)
                self.assertIn('error="invalid_token"', response["WWW-Authenticate"])
                self.assertNotIn(bearer, logs.records[0].getMessage())

    def test_foreign_origin_is_logged(self) -> None:
        with self.assertLogs("server.mcp", "WARNING"):
            response = self.client.post("/mcp", headers={"Origin": "https://evil.example"})

        self.assertEqual(response.status_code, 403)

    def test_non_post_is_405(self) -> None:
        response = self.client.get("/mcp")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "POST")

    def test_session_cookie_is_not_enough(self) -> None:
        self.client.force_login(self.user)

        self.assertEqual(self.client.post("/mcp").status_code, 401)

    def test_valid_token_authenticates(self) -> None:
        make_token(self.user)

        info = self.authenticate()

        assert info is not None  # noqa: S101
        self.assertEqual(info.user, self.user)
        self.assertEqual(info.scopes, frozenset({"hub:read"}))
        self.assertTrue(info.client_id)

    def test_valid_token_reaches_the_protocol(self) -> None:
        make_token(self.user)

        response = self.client.post(
            "/mcp",
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer tok",
        )

        self.assertEqual(response.status_code, 200)

    def test_token_for_other_resource_is_rejected(self) -> None:
        make_token(self.user, resource=["https://example.com/mcp"])

        self.assertIsNone(self.authenticate())

    def test_token_without_a_resource_is_rejected(self) -> None:
        make_token(self.user, resource=[])

        self.assertIsNone(self.authenticate())

    def test_expired_token_is_rejected(self) -> None:
        make_token(self.user, expires=now() - datetime.timedelta(seconds=1))

        self.assertIsNone(self.authenticate())

    def test_inactive_user_is_rejected(self) -> None:
        make_token(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        self.assertIsNone(self.authenticate())

    def test_token_without_a_user_is_rejected(self) -> None:
        token = make_token(self.user)
        token.user = None
        token.save()

        self.assertIsNone(self.authenticate())
        response = self.client.post("/mcp", headers={"Authorization": "Bearer tok"})
        self.assertEqual(response.status_code, 401)

    def test_unknown_token_is_rejected(self) -> None:
        self.assertIsNone(self.authenticate("nope"))

    def test_token_in_query_string_ignored(self) -> None:
        make_token(self.user)

        response = self.client.post("/mcp?access_token=tok")

        self.assertEqual(response.status_code, 401)


class TestMetadata(TestCase):
    def test_protected_resource_metadata(self) -> None:
        expected = {
            "resource": settings.MCP_RESOURCE_URL,
            "authorization_servers": [settings.PUBLIC_URL],
            "scopes_supported": ["hub:read", "hub:write"],
            "bearer_methods_supported": ["header"],
            "resource_name": "India Ultimate Hub",
        }
        for path in WELL_KNOWN[:2]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response.json(), expected, path)

    def test_authorization_server_metadata_advertises_cimd_and_pkce(self) -> None:
        data = self.client.get(WELL_KNOWN[2]).json()

        self.assertEqual(data["code_challenge_methods_supported"], ["S256"])
        self.assertIs(data["client_id_metadata_document_supported"], True)
        self.assertIn("none", data["token_endpoint_auth_methods_supported"])
        self.assertIs(data["authorization_response_iss_parameter_supported"], True)
        self.assertIn("registration_endpoint", data)
        self.assertEqual(data["response_types_supported"], ["code"])
        self.assertEqual(data["scopes_supported"], ["hub:read", "hub:write"])

    def test_disabled_returns_404(self) -> None:
        with override_settings(MCP_ENABLED=False):
            for path in ["/mcp", "/o/authorize/", "/o/token/", "/o/register/", *WELL_KNOWN]:
                self.assertEqual(self.client.post(path).status_code, 404, path)
                self.assertEqual(self.client.get(path).status_code, 404, path)


class TestConsent(McpAuthTestCase):
    def authorize_url(self, redirect_uri: str, client_id: str) -> str:
        return (
            f"/o/authorize/?response_type=code&client_id={client_id}"
            f"&redirect_uri={quote(redirect_uri, safe='')}&scope=hub%3Aread+hub%3Awrite"
            f"&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
            f"&code_challenge_method=S256&state=xyz"
            f"&resource={quote(settings.MCP_RESOURCE_URL, safe='')}"
        )

    def test_authorize_redirects_to_spa_login_with_redirect_param(self) -> None:
        application = make_token(self.user).application
        url = self.authorize_url("https://claude.ai/api/mcp/auth_callback", application.client_id)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/login?redirect={quote(url, safe='/')}")

    def test_consent_page_shows_client_scopes_and_redirect_host(self) -> None:
        application = make_token(self.user).application
        self.user.first_name, self.user.last_name = "Asha", "Rao"
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(
            self.authorize_url("https://claude.ai/api/mcp/auth_callback", application.client_id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mcp/consent.html")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Content-Security-Policy"], "frame-ancestors 'none'")
        html = response.content.decode()
        self.assertIn(f"Connect {application.name} to your Hub account?", html)
        self.assertIn(f"Signed in as <strong>{self.user.get_full_name()}</strong>", html)
        self.assertIn("<code>claude.ai</code>", html)
        self.assertIn("See your profile and membership, your teams and wards", html)
        self.assertIn("Make changes in Hub as you", html)
        self.assertIn("Pay for anything", html)
        self.assertIn('src="data:image/png;base64,', html)
        self.assertIn("Don't allow", html)
        self.assertNotIn("Runs on your computer", html)
        self.assertIn("Hub can't verify this name.", html)

    def test_claude_and_chatgpt_sign_in_with_their_published_documents(self) -> None:
        self.client.force_login(self.user)
        for document in (CLAUDE_DOCUMENT, CHATGPT_DOCUMENT):
            client_id, callback = document["client_id"], document["redirect_uris"][0]
            with (
                self.subTest(client=document["client_name"]),
                mock.patch.object(SafeMetadataFetcher, "fetch", return_value=(document, 300)),
            ):
                page = self.client.get(self.authorize_url(callback, client_id))
                location = self.allow(client_id, "S256", redirect_uri=callback)
                bearer = self.exchange(location, client_id, redirect_uri=callback)["access_token"]

                self.assertContains(page, f"Connect {document['client_name']}")
                application = Application.objects.get(client_id=client_id)
                self.assertEqual(Application.CLIENT_PUBLIC, application.client_type)
                self.assertEqual(
                    Application.GRANT_AUTHORIZATION_CODE, application.authorization_grant_type
                )
                self.assertIsNotNone(self.authenticate(bearer))

    def test_an_agent_signs_in_while_redis_times_out(self) -> None:
        self.client.force_login(self.user)
        client_id, callback = CLAUDE_DOCUMENT["client_id"], CLAUDE_DOCUMENT["redirect_uris"][0]
        self.addCleanup(store.reset)

        with (
            mock.patch.object(SafeMetadataFetcher, "fetch", return_value=(CLAUDE_DOCUMENT, 300)),
            mock.patch.object(cache, "get", side_effect=RedisTimeoutError("timed out")),
            mock.patch.object(cache, "set", side_effect=RedisTimeoutError("timed out")),
        ):
            page = self.client.get(self.authorize_url(callback, client_id))

        self.assertContains(page, "Connect Claude")

    def test_a_document_that_only_signs_with_a_key_is_refused(self) -> None:
        self.client.force_login(self.user)
        document = {
            **CHATGPT_DOCUMENT,
            "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        }

        with mock.patch.object(SafeMetadataFetcher, "fetch", return_value=(document, 300)):
            response = self.client.get(
                self.authorize_url(document["redirect_uris"][0], document["client_id"])
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Application.objects.filter(client_id=document["client_id"]).exists())

    def test_an_error_page_has_the_logo(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(
            self.authorize_url("https://claude.ai/api/mcp/auth_callback", "no-such-client")
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'src="data:image/png;base64,', status_code=400)

    def test_a_metadata_document_client_names_where_its_name_comes_from(self) -> None:
        application = make_token(self.user).application
        Application.objects.filter(pk=application.pk).update(
            client_id="https://agent.example/oauth/client.json"
        )
        self.client.force_login(self.user)

        response = self.client.get(
            self.authorize_url(
                "https://claude.ai/api/mcp/auth_callback", "https://agent.example/oauth/client.json"
            )
        )

        html = response.content.decode()
        self.assertIn("Its name comes from <code>agent.example</code>.", html)
        self.assertNotIn("Hub can't verify this name.", html)

    def test_a_read_only_request_lists_no_changes(self) -> None:
        application = make_token(self.user).application
        self.client.force_login(self.user)
        url = self.authorize_url("https://claude.ai/api/mcp/auth_callback", application.client_id)

        response = self.client.get(url.replace("scope=hub%3Aread+hub%3Awrite", "scope=hub%3Aread"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Make changes in Hub as you", response.content.decode())

    def test_loopback_client_gets_a_warning_and_any_port(self) -> None:
        application = make_token(self.user).application
        application.redirect_uris = "http://127.0.0.1/callback"
        application.save()
        self.client.force_login(self.user)

        response = self.client.get(
            self.authorize_url("http://127.0.0.1:54321/callback", application.client_id)
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Runs on your computer", html)
        self.assertIn("Only allow this if you started it just now", html)
        self.assertIn("Allow anyway", html)

    def test_other_redirect_uri_gets_a_friendly_page(self) -> None:
        application = make_token(self.user).application
        self.client.force_login(self.user)

        response = self.client.get(
            self.authorize_url("https://evil.example/cb", application.client_id)
        )

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "mcp/consent.html")
        self.assertIn("couldn't start this connection", response.content.decode())

    def allow(
        self,
        client_id: str,
        method: str,
        resource: str | None = "default",
        redirect_uri: str = "https://claude.ai/api/mcp/auth_callback",
    ) -> str:
        self.client.force_login(self.user)
        fields = {"resource": settings.MCP_RESOURCE_URL} if resource == "default" else {}
        response = self.client.post(
            "/o/authorize/",
            {
                **fields,
                "allow": "Authorize",
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "hub:read",
                "state": "xyz",
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": method,
            },
        )
        self.assertEqual(response.status_code, 302)
        return str(response["Location"])

    def exchange(
        self,
        location: str,
        client_id: str,
        redirect_uri: str = "https://claude.ai/api/mcp/auth_callback",
    ) -> dict[str, str]:
        code = parse_qs(urlparse(location).query)["code"][0]
        response = self.client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            },
        )
        self.assertEqual(response.status_code, 200)
        return dict(response.json())

    def test_missing_resource_defaults_to_the_mcp_url(self) -> None:
        application = make_token(self.user).application
        self.client.force_login(self.user)
        url = self.authorize_url("https://claude.ai/api/mcp/auth_callback", application.client_id)
        bare = url.split("&resource=")[0]

        page = self.client.get(bare)

        self.assertEqual(page.status_code, 200)
        self.assertIn(f'value="{settings.MCP_RESOURCE_URL}"', page.content.decode())
        location = self.allow(application.client_id, "S256", resource=None)
        bearer = self.exchange(location, application.client_id)["access_token"]
        self.assertIsNotNone(self.authenticate(bearer))

    def test_foreign_resource_is_refused(self) -> None:
        application = make_token(self.user).application
        self.client.force_login(self.user)
        url = self.authorize_url("https://claude.ai/api/mcp/auth_callback", application.client_id)
        foreign = url.split("&resource=")[0] + "&resource=https%3A%2F%2Fexample.com%2Fmcp"
        both = url + "&resource=https%3A%2F%2Fexample.com%2Fmcp"

        for refused in (foreign, both):
            response = self.client.get(refused)

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response["Content-Security-Policy"], "frame-ancestors 'none'")
            self.assertIn("couldn't start this connection", response.content.decode())
        post = self.client.post(
            "/o/authorize/",
            {
                "allow": "Authorize",
                "response_type": "code",
                "client_id": application.client_id,
                "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
                "scope": "hub:read",
                "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
                "code_challenge_method": "S256",
                "resource": "https://example.com/mcp",
            },
        )
        self.assertEqual(post.status_code, 400)
        self.assertIn("couldn't start this connection", post.content.decode())

    def test_approval_redirects_with_code_and_iss(self) -> None:
        application = make_token(self.user).application

        location = parse_qs(urlparse(self.allow(application.client_id, "S256")).query)

        self.assertIn("code", location)
        self.assertEqual(location["state"], ["xyz"])
        self.assertEqual(location["iss"], ["http://testserver"])

    def test_plain_pkce_is_refused(self) -> None:
        application = make_token(self.user).application

        location = self.allow(application.client_id, "plain")

        self.assertNotIn("code=", location)
        self.assertIn("error=invalid_request", location)


class TestRedirectPolicy(TestCase):
    def post_registration(self, body: Mapping[str, Any], **extra: Any) -> "Response":
        return self.client.post("/o/register/", body, content_type="application/json", **extra)

    def test_dcr_refuses_unhashable_grant_and_response_types(self) -> None:
        bad: list[dict[str, Any]] = [
            {"grant_types": [[1]]},
            {"response_types": [{"a": 1}]},
            {"grant_types": [1]},
        ]
        for extra in bad:
            response = self.post_registration(
                {"client_name": "App", "redirect_uris": ["http://localhost/cb"], **extra}
            )

            self.assertEqual(response.status_code, 400, extra)
            self.assertEqual(response.json()["error"], "invalid_client_metadata")

    def test_cimd_refuses_unhashable_grant_types(self) -> None:
        with self.assertRaises(CIMDError):
            self.fetch("http://localhost/cb", grant_types=[[1]])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_dcr_is_limited_to_10_an_hour_per_ip(self) -> None:
        cache.clear()
        body = {"client_name": "App", "redirect_uris": ["http://localhost/cb"]}
        for _ in range(10):
            self.assertEqual(self.post_registration(body, REMOTE_ADDR="1.1.1.1").status_code, 201)

        limited = self.post_registration(body, REMOTE_ADDR="1.1.1.1")

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"], "temporarily_unavailable")
        self.assertEqual(self.post_registration(body, REMOTE_ADDR="2.2.2.2").status_code, 201)
        self.assertEqual(
            self.post_registration(body, HTTP_FLY_CLIENT_IP="3.3.3.3").status_code, 201
        )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_a_cache_outage_does_not_block_registration(self) -> None:
        self.addCleanup(store._state.update, down_until=0.0)
        body = {"client_name": "App", "redirect_uris": ["http://localhost/cb"]}
        with mock.patch.object(cache, "add", side_effect=ConnectionError("redis down")):
            self.assertEqual(self.post_registration(body).status_code, 201)

    def register(self, *uris: str) -> int:
        response = self.client.post(
            "/o/register/",
            {
                "client_name": "App",
                "redirect_uris": list(uris),
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code"],
            },
            content_type="application/json",
        )
        return response.status_code

    def test_dcr_refuses_foreign_https_and_non_loopback_http(self) -> None:
        self.assertEqual(self.register("https://evil.example/cb"), 400)
        self.assertEqual(self.register("http://evil.example/cb"), 400)
        self.assertEqual(self.register("http://127.0.0.1.evil.example/cb"), 400)
        self.assertEqual(self.register("https://claude.ai/api/mcp/auth_callback/x"), 400)
        self.assertEqual(self.register("https://chatgpt.com/connector/oauth/abc"), 400)
        self.assertEqual(
            self.register("https://chatgpt.com.evil.example/connector_platform_oauth_redirect"), 400
        )
        self.assertEqual(
            self.register("https://claude.ai/api/mcp/auth_callback", "https://evil.example/cb"),
            400,
        )
        self.assertFalse(Application.objects.exists())

    def test_dcr_refuses_a_second_address_smuggled_behind_whitespace(self) -> None:
        for gap in [" ", "\n", "\t", "\r", "\x0b", "\u00a0", "\x00"]:
            uri = f"http://localhost/{gap}https://evil.example/cb"
            self.assertEqual(self.register(uri), 400, repr(gap))
        self.assertEqual(self.register(""), 400)
        self.assertFalse(Application.objects.exists())

    def test_dcr_refuses_redirect_uris_that_is_not_a_list(self) -> None:
        response = self.client.post(
            "/o/register/",
            {"client_name": "App", "redirect_uris": "http://localhost/cb"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_dcr_refuses_grant_and_response_types_that_mint_user_less_tokens(self) -> None:
        for extra in [
            {"grant_types": ["client_credentials"]},
            {"grant_types": ["authorization_code", "client_credentials"]},
            {"grant_types": ["implicit"]},
            {"response_types": ["token"]},
        ]:
            response = self.client.post(
                "/o/register/",
                {
                    "client_name": "App",
                    "redirect_uris": ["http://localhost/cb"],
                    "token_endpoint_auth_method": "client_secret_basic",
                    **extra,
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, extra)
        self.assertFalse(Application.objects.exists())

    def test_dcr_update_refuses_client_credentials(self) -> None:
        created = self.client.post(
            "/o/register/",
            {"client_name": "App", "redirect_uris": ["http://localhost/cb"]},
            content_type="application/json",
        ).json()

        response = self.client.put(
            created["registration_client_uri"],
            {
                "client_name": "App",
                "redirect_uris": ["http://localhost/cb"],
                "grant_types": ["client_credentials"],
            },
            content_type="application/json",
            headers={"Authorization": f"Bearer {created['registration_access_token']}"},
        )

        self.assertEqual(response.status_code, 400)

    def test_dcr_accepts_hosted_agents_and_loopback(self) -> None:
        for uri in [
            "https://claude.ai/api/mcp/auth_callback",
            "https://chatgpt.com/connector_platform_oauth_redirect",
            "http://localhost:8123/callback",
            "http://127.0.0.1/cb",
            "http://[::1]:9/cb",
        ]:
            self.assertEqual(self.register(uri), 201, uri)

    def fetch(self, *uris: str, **extra: object) -> Any:
        document = {"redirect_uris": list(uris), "client_name": "App", **extra}
        with mock.patch.object(SafeMetadataFetcher, "fetch", return_value=(document, 300)):
            return PolicyMetadataFetcher().fetch("https://app.example/client.json")

    def test_cimd_refuses_a_foreign_redirect(self) -> None:
        with self.assertRaises(CIMDError):
            self.fetch("https://evil.example/cb")
        with self.assertRaises(CIMDError):
            self.fetch("http://evil.example/cb")

    def test_cimd_refuses_a_second_address_smuggled_behind_whitespace(self) -> None:
        for gap in [" ", "\n", "\t"]:
            with self.assertRaises(CIMDError):
                self.fetch(f"http://localhost/{gap}https://evil.example/cb")

    def test_cimd_refuses_client_credentials(self) -> None:
        with self.assertRaises(CIMDError):
            self.fetch("http://localhost/cb", grant_types=["client_credentials"])
        with self.assertRaises(CIMDError):
            self.fetch("http://localhost/cb", response_types=["token"])

    def test_cimd_keeps_only_the_grants_and_auth_hub_offers(self) -> None:
        document, _ = self.fetch(
            "http://localhost/cb",
            grant_types=["authorization_code", "client_credentials", JWT_BEARER],
            token_endpoint_auth_method="private_key_jwt",  # noqa: S106
            token_endpoint_auth_methods_supported=["none", "private_key_jwt"],
        )

        self.assertEqual(document["grant_types"], ["authorization_code"])
        self.assertEqual(document["token_endpoint_auth_method"], "none")

    def test_cimd_refuses_a_client_without_the_authorization_code_grant(self) -> None:
        with self.assertRaises(CIMDError):
            self.fetch("http://localhost/cb", grant_types=[JWT_BEARER])

    def test_cimd_accepts_hosted_agents_and_loopback(self) -> None:
        self.fetch(
            "https://claude.ai/api/mcp/auth_callback",
            "https://chatgpt.com/connector_platform_oauth_redirect",
            "http://localhost:5/cb",
        )

    def test_refresh_tokens_expire_after_30_days(self) -> None:
        self.assertEqual(oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS, 60 * 60 * 24 * 30)


class TestMergeDropsTokens(MergeTestCase):
    def test_merge_deletes_absorbed_users_tokens(self) -> None:
        make_token(self.duplicate, "dup-token")
        make_token(self.primary, "primary-token")

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertEqual(
            list(AccessToken.objects.values_list("token", flat=True)), ["primary-token"]
        )
        self.assertEqual(set(Application.objects.values_list("user", flat=True)), {self.primary.pk})

    def test_another_users_token_on_the_absorbed_users_app_survives(self) -> None:
        theirs = make_token(self.duplicate, "dup-token")
        other = User.objects.create(username="o@x.com", email="o@x.com")
        value = "other-token"
        AccessToken.objects.create(
            user=other,
            application=theirs.application,
            token=value,
            scope="hub:read",
            expires=now() + datetime.timedelta(hours=1),
            resource=[settings.MCP_RESOURCE_URL],
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        token = AccessToken.objects.get(token=value)
        self.assertEqual(token.user, other)
        self.assertEqual(token.application.user, self.primary)
