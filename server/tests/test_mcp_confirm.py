import datetime
import time
from io import StringIO
from typing import TYPE_CHECKING, Any
from unittest import mock

from django.core import signing
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils.timezone import now

from server.core.models import User
from server.mcp import registry
from server.mcp.confirm import confirm_then
from server.mcp.models import McpNonce
from server.mcp.registry import ToolContext, ToolResult, fail, ok
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import (
    CAPS,
    VERSION,
    McpProtocolTestCase,
    modern_headers,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

MESSAGE = "Pay 500 rupees"
SCHEMA = {
    "type": "object",
    "properties": {"amount": {"type": "integer"}},
    "additionalProperties": False,
}
FORM: dict[str, Any] = {"elicitation": {"form": {}}}
NOT_DONE = "Not done: you said no."


class ConfirmTestCase(McpProtocolTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.runs = 0
        self.failing = False
        self.raising = False

        def handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
            def action() -> ToolResult:
                self.runs += 1
                if self.raising:
                    raise RuntimeError("the email service is down")
                return fail("nope") if self.failing else ok({"done": True})

            return confirm_then(ctx, message=MESSAGE, binding=args, action=action)

        self.add_tool("t_write", handler, input_schema=SCHEMA, writes=True)
        self.add_tool("t_other", handler, input_schema=SCHEMA, writes=True)
        make_token(self.user, "wtok", scope="hub:read hub:write")

    def send(
        self,
        arguments: dict[str, Any] | None = None,
        capabilities: dict[str, Any] | None = None,
        bearer: str = "wtok",
        **extra: Any,
    ) -> "Response":
        meta = {VERSION: "2026-07-28", CAPS: capabilities or {}}
        params = {
            "name": "t_write",
            "arguments": {"amount": 500} if arguments is None else arguments,
            **extra,
            "_meta": meta,
        }
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        return self.post(body, modern_headers(body), bearer)

    def legacy_call(self) -> "Response":
        params = {"name": "t_write", "arguments": {"amount": 500}}
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        return self.post(body, bearer="wtok")

    def ask(self, **kw: Any) -> str:
        result = self.send(capabilities=FORM, **kw).json()["result"]
        self.assertEqual("input_required", result["resultType"])
        state: str = result["requestState"]
        return state

    def answer(self, state: str, response: Any, **kw: Any) -> dict[str, Any]:
        responses = {"confirm": response} if response else {}
        result: dict[str, Any] = self.send(
            capabilities=FORM, inputResponses=responses, requestState=state, **kw
        ).json()["result"]
        return result


YES = {"action": "accept", "content": {"confirm": True}}


class TestElicitation(ConfirmTestCase):
    def test_first_call_asks(self) -> None:
        result = self.send(capabilities=FORM).json()["result"]

        self.assertEqual("input_required", result["resultType"])
        request = result["inputRequests"]["confirm"]
        self.assertEqual("elicitation/create", request["method"])
        self.assertEqual("form", request["params"]["mode"])
        self.assertEqual(MESSAGE, request["params"]["message"])
        self.assertEqual(
            {
                "type": "object",
                "properties": {"confirm": {"type": "boolean", "title": "Yes, do this"}},
                "required": ["confirm"],
            },
            request["params"]["requestedSchema"],
        )
        self.assertTrue(result["requestState"])
        self.assertNotIn("ttlMs", result)
        self.assertEqual(0, self.runs)

    def test_empty_elicitation_capability_means_form(self) -> None:
        result = self.send(capabilities={"elicitation": {}}).json()["result"]

        self.assertEqual("input_required", result["resultType"])

    def test_accept_runs_once(self) -> None:
        state = self.ask()

        result = self.answer(state, YES)

        self.assertTrue(result["structuredContent"]["done"])
        self.assertEqual(1, self.runs)

    def test_decline_and_cancel(self) -> None:
        for action, text in [
            ("decline", NOT_DONE),
            ("accept", NOT_DONE),
        ]:
            with self.subTest(action):
                state = self.ask()
                content = {"confirm": False} if action == "accept" else {}

                result = self.answer(state, {"action": action, "content": content})

                self.assertEqual({"done": False, "message": text}, result["structuredContent"])
                self.assertFalse(result["isError"])
                self.assertEqual(0, self.runs)

    def test_missing_response_asks_again(self) -> None:
        state = self.ask()

        result = self.answer(state, None)

        self.assertEqual("input_required", result["resultType"])
        self.assertEqual(0, self.runs)

    def test_rejections(self) -> None:
        make_token(User.objects.create(username="b@x.com"), "btok", scope="hub:write")
        used = self.ask()
        self.answer(used, YES)
        cases: dict[str, tuple[str, dict[str, Any], str]] = {
            "reused": (used, {}, "wtok"),
            "other user": (self.ask(), {}, "btok"),
            "tampered": (self.ask()[:-3] + "xyz", {}, "wtok"),
        }
        for name, (state, kw, bearer) in cases.items():
            with self.subTest(name):
                self.runs = 0
                result = self.answer(state, YES, bearer=bearer, **kw)

                self.assertTrue(result["isError"])
                self.assertTrue(result["structuredContent"]["message"])
                self.assertEqual(0, self.runs)

    def test_expired(self) -> None:
        stale = signing.b62_encode(int(time.time()) - 601)
        with mock.patch.object(signing.TimestampSigner, "timestamp", return_value=stale):
            state = self.ask()

        result = self.answer(state, YES)

        self.assertTrue(result["isError"])
        self.assertIn("expired", result["structuredContent"]["message"])
        self.assertEqual(0, self.runs)

    def test_failed_action_leaves_no_nonce(self) -> None:
        state = self.ask()
        self.failing = True

        self.assertTrue(self.answer(state, YES)["isError"])
        self.assertEqual(0, McpNonce.objects.count())

        self.failing = False
        self.assertFalse(self.answer(state, YES)["isError"])
        self.assertEqual(1, McpNonce.objects.count())

    def test_a_raising_action_keeps_its_nonce_so_a_retry_cannot_repeat_it(self) -> None:
        state = self.ask()
        self.raising = True

        self.assertTrue(self.answer(state, YES)["isError"])
        self.assertEqual(1, McpNonce.objects.count())

        self.raising = False
        retry = self.answer(state, YES)
        self.assertTrue(retry["isError"])
        self.assertIn("already used", retry["structuredContent"]["message"])
        self.assertEqual(1, self.runs)

    def test_a_closed_dialog_asks_in_chat_instead(self) -> None:
        state = self.ask()

        data = self.answer(state, {"action": "cancel"})["structuredContent"]

        self.assertFalse(data["done"])
        self.assertTrue(data["needs_confirmation"].startswith("The question was closed"))
        self.assertIn(
            "only call again with this confirmation if they say yes", data["needs_confirmation"]
        )
        self.assertEqual(0, self.runs)
        result = self.send({"amount": 500, "confirmation": data["confirmation"]}, capabilities=FORM)
        self.assertTrue(result.json()["result"]["structuredContent"]["done"])
        self.assertEqual(1, self.runs)

    def test_a_dialog_state_is_not_a_chat_confirmation(self) -> None:
        state = self.ask()

        result = self.send({"amount": 500, "confirmation": state}, capabilities=FORM).json()[
            "result"
        ]

        self.assertTrue(result["isError"])
        self.assertEqual(0, self.runs)

    def test_a_changed_request_is_asked_again(self) -> None:
        state = self.ask()

        result = self.answer(state, YES, arguments={"amount": 900})

        self.assertEqual("input_required", result["resultType"])
        message = result["inputRequests"]["confirm"]["params"]["message"]
        self.assertTrue(message.startswith("Something changed"))
        self.assertEqual(0, self.runs)

    def test_a_state_for_another_tool_is_refused(self) -> None:
        state = self.ask()

        result = self.answer(state, YES, name="t_other")

        self.assertTrue(result["isError"])
        self.assertIn("different request", result["structuredContent"]["message"])
        self.assertEqual(0, self.runs)


class TestFallback(ConfirmTestCase):
    def first(self, modern: bool) -> dict[str, Any]:
        if modern:
            result: dict[str, Any] = self.send().json()["result"]
        else:
            result = self.legacy_call().json()["result"]
        return result["structuredContent"]

    def test_asks_in_chat(self) -> None:
        for modern in (True, False):
            with self.subTest(modern=modern):
                data = self.first(modern)

                self.assertEqual(
                    {
                        "done": False,
                        "needs_confirmation": MESSAGE,
                        "confirmation": data["confirmation"],
                        "how": "Show this to the user. Call again with the same arguments "
                        "and this confirmation only if they say yes.",
                    },
                    data,
                )
                self.assertTrue(data["confirmation"])
        self.assertEqual(0, self.runs)

    def test_confirmation_runs_once(self) -> None:
        code = self.first(True)["confirmation"]

        result = self.send({"amount": 500, "confirmation": code}).json()["result"]

        self.assertTrue(result["structuredContent"]["done"])
        self.assertEqual(1, self.runs)

        again = self.send({"amount": 500, "confirmation": code}).json()["result"]
        self.assertTrue(again["isError"])
        self.assertEqual(1, self.runs)

    def test_confirmation_for_changed_args_asks_again(self) -> None:
        code = self.first(False)["confirmation"]

        data = self.send({"amount": 9, "confirmation": code}).json()["result"]["structuredContent"]

        self.assertFalse(data["done"])
        self.assertTrue(data["needs_confirmation"].startswith("Something changed"))
        self.assertNotEqual(code, data["confirmation"])
        self.assertEqual(0, self.runs)

    def test_writes_get_a_confirmation_property(self) -> None:
        self.add_tool("t_read", input_schema=SCHEMA)
        make_token(self.user, "rtok")

        tools = {t["name"]: t for t in self.modern("tools/list").json()["result"]["tools"]}

        confirmation = tools["t_write"]["inputSchema"]["properties"]["confirmation"]
        self.assertEqual("string", confirmation["type"])
        self.assertIn("Leave out on the first call", confirmation["description"])
        self.assertNotIn("confirmation", tools["t_read"]["inputSchema"]["properties"])


class TestCleanup(ConfirmTestCase):
    def test_deletes_only_expired(self) -> None:
        McpNonce.objects.create(key="old", expires_at=now() - datetime.timedelta(seconds=1))
        McpNonce.objects.create(key="new", expires_at=now() + datetime.timedelta(minutes=5))

        call_command("cleanup_mcp_nonces", stdout=StringIO())

        self.assertEqual(["new"], list(McpNonce.objects.values_list("key", flat=True)))


class TestEmailBudget(ConfirmTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.add_tool(
            "t_mail",
            registry.TOOLS["t_write"].handler,
            input_schema=SCHEMA,
            writes=True,
            emails=True,
        )
        cache_override = override_settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        )
        cache_override.enable()
        self.addCleanup(cache_override.disable)
        self.addCleanup(cache.clear)
        patch = mock.patch.object(registry, "EMAIL_RATE_LIMIT", 1)
        patch.start()
        self.addCleanup(patch.stop)

    def mail(self, state: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"name": "t_mail", "arguments": {"amount": 500}}
        if state:
            params |= {"requestState": state, "inputResponses": {"confirm": YES}}
        params["_meta"] = {VERSION: "2026-07-28", CAPS: FORM}
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        result: dict[str, Any] = self.post(body, modern_headers(body), "wtok").json()["result"]
        return result

    def test_a_preview_spends_nothing_and_a_confirmed_run_spends_one(self) -> None:
        for _ in range(3):
            state = self.mail()["requestState"]

        self.assertFalse(self.mail(state)["isError"])
        self.assertTrue(self.mail(self.mail()["requestState"])["isError"])
        self.assertEqual(1, self.runs)

    def test_over_the_limit_the_nonce_is_not_burned(self) -> None:
        self.assertFalse(self.mail(self.mail()["requestState"])["isError"])
        state = self.mail()["requestState"]

        result = self.mail(state)

        self.assertIn("sent a lot of emails", result["structuredContent"]["message"])
        self.assertEqual(1, McpNonce.objects.count())
        self.assertEqual(1, self.runs)

    def test_a_tool_without_emails_is_never_limited(self) -> None:
        for _ in range(3):
            self.assertFalse(self.answer(self.ask(), YES)["isError"])

    def test_each_recipient_counts(self) -> None:
        ctx = mock.Mock(user=self.user)

        self.assertIsNotNone(registry.spend_email_budget(ctx, sends=2))
        self.assertIsNone(registry.spend_email_budget(mock.Mock(user=User(pk=999))))

    def test_a_run_that_emails_nobody_is_never_limited(self) -> None:
        def handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
            def action() -> ToolResult:
                self.runs += 1
                return ok({"done": True})

            return confirm_then(ctx, message=MESSAGE, binding=args, action=action, emails=0)

        self.add_tool("t_mail", handler, input_schema=SCHEMA, writes=True, emails=True)
        for _ in range(3):
            self.assertFalse(self.mail(self.mail()["requestState"])["isError"])
        self.assertEqual(3, self.runs)
