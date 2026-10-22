import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from server.cache import store
from server.committee.models import Committee
from server.committee.models import Role as CommitteeRole
from server.core.models import Guardianship, Player, Team, UCPerson, User
from server.mcp import protocol, registry
from server.mcp.registry import Audience, ToolContext, ToolResult, ok
from server.payment_account.models import PaymentAccount
from server.tests.base import create_event
from server.tests.test_mcp_auth import make_token
from server.tournament.models import Registration, Tournament, UCRegistration

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

VERSION = "io.modelcontextprotocol/protocolVersion"
CAPS = "io.modelcontextprotocol/clientCapabilities"
NO_ARGS = {"type": "object", "additionalProperties": False}


def modern_body(method: str, params: dict[str, Any] | None = None, **fields: Any) -> dict[str, Any]:
    meta = {VERSION: "2026-07-28", CAPS: {}}
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": {**(params or {}), "_meta": meta},
        **fields,
    }


def modern_headers(body: dict[str, Any]) -> dict[str, str]:
    headers = {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": body["method"]}
    if body["method"] == "tools/call":
        headers["Mcp-Name"] = body["params"]["name"]
    return headers


class McpProtocolTestCase(TestCase):
    bearer = "tok"

    def setUp(self) -> None:
        self.user = User.objects.create(
            username="a@x.com", email="a@x.com", first_name="Asha", last_name="Rao"
        )
        make_token(self.user, "tok", scope="hub:read")
        self.addCleanup(self.restore_registry, dict(registry.TOOLS))

    @staticmethod
    def restore_registry(saved: dict[str, registry.Tool]) -> None:
        registry.TOOLS.clear()
        registry.TOOLS.update(saved)

    def post(
        self, body: Any, headers: dict[str, str] | None = None, bearer: str = "tok"
    ) -> "Response":
        data = body if isinstance(body, str) else json.dumps(body)
        return self.client.post(
            "/mcp",
            data=data,
            content_type="application/json",
            headers={"Authorization": f"Bearer {bearer}", **(headers or {})},
        )

    def modern(
        self, method: str, params: dict[str, Any] | None = None, bearer: str = "tok"
    ) -> "Response":
        body = modern_body(method, params)
        return self.post(body, modern_headers(body), bearer)

    def call(
        self, name: str, arguments: dict[str, Any], bearer: str | None = None
    ) -> dict[str, Any]:
        params = {"name": name, "arguments": arguments}
        body = self.modern("tools/call", params, bearer or self.bearer).json()
        return dict(body.get("result") or body)

    def keys(self, data: Any) -> set[str]:
        if isinstance(data, dict):
            return set(data) | {k for v in data.values() for k in self.keys(v)}
        if isinstance(data, list):
            return {k for v in data for k in self.keys(v)}
        return set()

    def legacy(self, method: str, params: dict[str, Any] | None = None) -> "Response":
        return self.post({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def add_tool(
        self, name: str, handler: Callable[..., ToolResult] | None = None, **kw: Any
    ) -> None:
        registry.tool(
            name, title=name, description="test", input_schema=kw.pop("input_schema", NO_ARGS), **kw
        )(handler or (lambda ctx, args: ok({"done": True})))

    def names(self, response: "Response") -> list[str]:
        return [t["name"] for t in response.json()["result"]["tools"]]


class TestHandshake(McpProtocolTestCase):
    def test_discover(self) -> None:
        response = self.modern("server/discover")

        self.assertEqual(200, response.status_code)
        result = response.json()["result"]
        self.assertEqual("complete", result["resultType"])
        self.assertEqual(["2026-07-28", "2025-11-25"], result["supportedVersions"])
        self.assertEqual({"tools": {"listChanged": False}}, result["capabilities"])
        self.assertEqual("hub", result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"])
        self.assertEqual(300000, result["ttlMs"])
        self.assertEqual("private", result["cacheScope"])
        self.assertLessEqual(len(result["instructions"]), 4096)

    def test_initialize_echoes_supported_versions(self) -> None:
        for asked, expected in [
            ("2025-11-25", "2025-11-25"),
            ("2025-06-18", "2025-06-18"),
            ("1999-01-01", "2025-11-25"),
        ]:
            with self.subTest(asked=asked):
                result = self.legacy("initialize", {"protocolVersion": asked}).json()["result"]

                self.assertEqual(expected, result["protocolVersion"])
                self.assertEqual({"tools": {"listChanged": False}}, result["capabilities"])
                self.assertEqual("hub", result["serverInfo"]["name"])
                self.assertEqual(protocol.INSTRUCTIONS, result["instructions"])

    def test_modern_ids_are_echoed_exactly(self) -> None:
        for request_id in ("abc", 7, 0):
            with self.subTest(id=request_id):
                body = modern_body("tools/list")
                body["id"] = request_id

                response = self.post(body, modern_headers(body))

                self.assertEqual(request_id, response.json()["id"])
                self.assertIs(type(request_id), type(response.json()["id"]))

    def test_session_cookie_without_bearer_is_401_on_modern(self) -> None:
        self.client.force_login(self.user)
        body = modern_body("tools/list")

        response = self.client.post(
            "/mcp", json.dumps(body), content_type="application/json", headers=modern_headers(body)
        )

        self.assertEqual(401, response.status_code)

    def test_deeply_nested_json_is_parse_error(self) -> None:
        response = self.post("[" * 100000)

        self.assertEqual(-32700, response.json()["error"]["code"])

    def test_notification_is_202_with_no_body(self) -> None:
        response = self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})

        self.assertEqual(202, response.status_code)
        self.assertEqual(b"", response.content)

    def test_ids_are_echoed_exactly(self) -> None:
        for request_id in ("abc", 7, 0):
            with self.subTest(id=request_id):
                response = self.post({"jsonrpc": "2.0", "id": request_id, "method": "ping"})

                self.assertEqual(request_id, response.json()["id"])
                self.assertIs(type(request_id), type(response.json()["id"]))


class TestTools(McpProtocolTestCase):
    def test_list_is_sorted_and_well_formed(self) -> None:
        self.add_tool("aaa_first")

        response = self.modern("tools/list")

        result = response.json()["result"]
        names = self.names(response)
        self.assertEqual(sorted(names), names)
        self.assertEqual("aaa_first", names[0])
        self.assertIn("whoami", names)
        self.assertEqual("complete", result["resultType"])
        self.assertEqual(300000, result["ttlMs"])
        self.assertEqual("private", result["cacheScope"])
        for tool in result["tools"]:
            self.assertRegex(tool["name"], r"^[a-z0-9_]{1,64}$")
            self.assertTrue(tool["title"])
            self.assertEqual("object", tool["inputSchema"]["type"])
            self.assertIs(
                not registry.TOOLS[tool["name"]].writes, tool["annotations"]["readOnlyHint"]
            )

    def test_legacy_list_has_plain_result(self) -> None:
        result = self.legacy("tools/list").json()["result"]

        self.assertEqual(["tools"], list(result))

    def test_staff_tool_only_for_staff(self) -> None:
        self.add_tool("staff_only", audience=Audience.STAFF)
        self.assertNotIn("staff_only", self.names(self.modern("tools/list")))

        self.user.is_staff = True
        self.user.save()

        self.assertIn("staff_only", self.names(self.modern("tools/list")))

    def test_team_admin_tool_only_for_team_admins(self) -> None:
        self.add_tool("team_only", audience=Audience.TEAM_ADMIN)
        self.assertNotIn("team_only", self.names(self.modern("tools/list")))

        Team.objects.create(name="Bangalore").admins.add(self.user)

        self.assertIn("team_only", self.names(self.modern("tools/list")))

    def test_hidden_tool_cannot_be_called(self) -> None:
        self.add_tool("staff_only", audience=Audience.STAFF)

        response = self.modern("tools/call", {"name": "staff_only", "arguments": {}})

        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_whoami(self) -> None:
        response = self.modern("tools/call", {"name": "whoami", "arguments": {}})

        result = response.json()["result"]
        self.assertEqual("complete", result["resultType"])
        self.assertFalse(result["isError"])
        self.assertEqual("text", result["content"][0]["type"])
        self.assertEqual(result["structuredContent"], json.loads(result["content"][0]["text"]))
        data = result["structuredContent"]
        self.assertEqual(self.user.pk, data["user_id"])
        self.assertIsNone(data["player_id"])
        self.assertEqual([], data["wards"])
        self.assertEqual([], data["admin_teams"])
        self.assertNotIn("id", self.keys(data))

    def test_whoami_names_player_ward_and_team_ids(self) -> None:
        player = Player.objects.create(user=self.user, date_of_birth="1990-01-01", gender="F")
        ward_user = User.objects.create(username="w@x.com", email="w@x.com")
        ward = Player.objects.create(user=ward_user, date_of_birth="2012-01-01", gender="M")
        Guardianship.objects.create(user=self.user, player=ward, relation="MO")
        team = Team.objects.create(name="Bangalore", slug="bangalore")
        team.admins.add(self.user)

        data = self.modern("tools/call", {"name": "whoami", "arguments": {}}).json()["result"][
            "structuredContent"
        ]

        self.assertEqual(player.pk, data["player_id"])
        self.assertEqual([ward.pk], [w["player_id"] for w in data["wards"]])
        self.assertEqual(
            [(team.pk, "bangalore")], [(t["team_id"], t["team_slug"]) for t in data["admin_teams"]]
        )
        self.assertNotIn("id", self.keys(data))

    def test_unknown_tool_is_a_protocol_error(self) -> None:
        response = self.modern("tools/call", {"name": "nope", "arguments": {}})

        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_bad_arguments_are_tool_errors_naming_the_field(self) -> None:
        self.add_tool(
            "typed",
            input_schema={
                "type": "object",
                "properties": {"team_id": {"type": "integer"}},
                "required": ["team_id"],
                "additionalProperties": False,
            },
        )
        for arguments, field in [
            ({"team_id": "x"}, "team_id"),
            ({"team_id": 1, "extra": 1}, "extra"),
            ({}, "team_id"),
        ]:
            with self.subTest(arguments=arguments):
                response = self.modern("tools/call", {"name": "typed", "arguments": arguments})

                result = response.json()["result"]
                self.assertTrue(result["isError"])
                self.assertIn(field, result["content"][0]["text"])

    def test_handler_exception_is_hidden(self) -> None:
        def boom(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
            raise RuntimeError("secret detail")

        self.add_tool("boom", boom)

        with self.assertLogs("server.mcp", "ERROR"):
            response = self.modern("tools/call", {"name": "boom", "arguments": {}})

        self.assertTrue(response.json()["result"]["isError"])
        self.assertNotIn("secret detail", response.content.decode())

    def test_write_tool_needs_write_scope(self) -> None:
        self.add_tool("change", writes=True)

        response = self.modern("tools/call", {"name": "change", "arguments": {}})

        self.assertEqual(403, response.status_code)
        self.assertIn('error="insufficient_scope"', response["WWW-Authenticate"])

    def test_write_tool_runs_with_write_scope(self) -> None:
        self.add_tool("change", writes=True)
        make_token(self.user, "rw", scope="hub:read hub:write")

        response = self.modern("tools/call", {"name": "change", "arguments": {}}, bearer="rw")

        self.assertEqual({"done": True}, response.json()["result"]["structuredContent"])

    def test_write_tool_annotations(self) -> None:
        self.add_tool("change", writes=True, destructive=True)

        tool = next(
            t for t in self.modern("tools/list").json()["result"]["tools"] if t["name"] == "change"
        )

        self.assertIs(False, tool["annotations"]["readOnlyHint"])
        self.assertIs(True, tool["annotations"]["destructiveHint"])

    def test_rate_limit(self) -> None:
        with (
            override_settings(
                CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
            ),
            mock.patch.object(protocol, "RATE_LIMIT", 1),
        ):
            first = self.modern("tools/call", {"name": "whoami", "arguments": {}})
            second = self.modern("tools/call", {"name": "whoami", "arguments": {}})

        self.assertFalse(first.json()["result"]["isError"])
        self.assertTrue(second.json()["result"]["isError"])
        self.assertIn("wait a minute", second.json()["result"]["content"][0]["text"])

    def test_the_audit_logger_is_not_silenced_by_the_root_level(self) -> None:
        self.assertLessEqual(logging.getLogger("server.mcp").getEffectiveLevel(), logging.INFO)

    def test_a_cache_outage_does_not_block_calls(self) -> None:
        self.addCleanup(store._state.update, down_until=0.0)
        with mock.patch.object(cache, "add", side_effect=ConnectionError("redis down")):
            response = self.modern("tools/call", {"name": "whoami", "arguments": {}})

        self.assertFalse(response.json()["result"]["isError"])

    def test_read_tool_needs_read_scope(self) -> None:
        make_token(self.user, "w", scope="hub:write")

        response = self.modern("tools/call", {"name": "whoami", "arguments": {}}, bearer="w")

        self.assertEqual(403, response.status_code)
        self.assertIn('error="insufficient_scope"', response["WWW-Authenticate"])

    def test_audit_line_carries_the_traceparent(self) -> None:
        trace = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        body = modern_body("tools/call", {"name": "whoami", "arguments": {}})
        body["params"]["_meta"]["traceparent"] = trace

        with self.assertLogs("server.mcp", "INFO") as logs:
            self.post(body, modern_headers(body))
        self.assertEqual(trace, json.loads(logs.records[0].getMessage())["traceparent"])

        with self.assertLogs("server.mcp", "INFO") as logs:
            self.legacy("tools/call", {"name": "whoami", "arguments": {}})
        self.assertNotIn("traceparent", json.loads(logs.records[0].getMessage()))

        with self.assertLogs("server.mcp", "INFO") as logs:
            self.post(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "whoami", "arguments": {}},
                },
                {"traceparent": trace},
            )
        self.assertEqual(trace, json.loads(logs.records[0].getMessage())["traceparent"])

    def test_audit_line_has_no_raw_arguments(self) -> None:
        with self.assertLogs("server.mcp", "INFO") as logs:
            self.modern("tools/call", {"name": "whoami", "arguments": {}})

        line = json.loads(logs.records[0].getMessage())
        self.assertEqual(
            ["args_digest", "client_id", "method", "ms", "outcome", "tool", "user_id"], sorted(line)
        )
        self.assertEqual(
            ("whoami", "ok", "tools/call"), (line["tool"], line["outcome"], line["method"])
        )
        self.assertEqual(16, len(line["args_digest"]))


class TestModernValidation(McpProtocolTestCase):
    def send(self, headers: dict[str, str], params: dict[str, Any] | None = None) -> "Response":
        body = modern_body("tools/call", params or {"name": "whoami", "arguments": {}})
        return self.post(body, headers)

    def good(self) -> dict[str, str]:
        return {
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": "whoami",
        }

    def test_header_mismatches_are_32020(self) -> None:
        for drop, replace in [
            ("MCP-Protocol-Version", None),
            ("Mcp-Method", "tools/list"),
            ("Mcp-Name", "other"),
            ("Mcp-Name", "=?base64?!!!?="),
        ]:
            headers = self.good()
            del headers[drop]
            if replace:
                headers[drop] = replace
            with self.subTest(drop=drop, replace=replace):
                response = self.send(headers)

                self.assertEqual(400, response.status_code)
                self.assertEqual(-32020, response.json()["error"]["code"])

    def test_base64_name_is_accepted(self) -> None:
        headers = {**self.good(), "Mcp-Name": "=?base64?d2hvYW1p?="}

        self.assertEqual(200, self.send(headers).status_code)

    def test_unsupported_version(self) -> None:
        body = modern_body("tools/list")
        body["params"]["_meta"][VERSION] = "2027-01-01"

        response = self.post(
            body, {"MCP-Protocol-Version": "2027-01-01", "Mcp-Method": "tools/list"}
        )

        self.assertEqual(400, response.status_code)
        error = response.json()["error"]
        self.assertEqual(-32022, error["code"])
        self.assertEqual(
            {"supported": ["2026-07-28", "2025-11-25"], "requested": "2027-01-01"}, error["data"]
        )

    def test_missing_client_capabilities(self) -> None:
        body = modern_body("tools/list")
        del body["params"]["_meta"][CAPS]

        response = self.post(body, modern_headers(body))

        self.assertEqual(400, response.status_code)
        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_unknown_method_status_depends_on_era(self) -> None:
        modern = self.modern("resources/list")
        legacy = self.legacy("resources/list")

        self.assertEqual(404, modern.status_code)
        self.assertEqual(-32601, modern.json()["error"]["code"])
        self.assertEqual(200, legacy.status_code)
        self.assertEqual(-32601, legacy.json()["error"]["code"])

    def test_modern_header_without_meta_is_invalid_params(self) -> None:
        headers = {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"}
        bad: list[dict[str, Any]] = [
            {},
            {"_meta": {CAPS: {}}},
            {"_meta": {VERSION: "2026-07-28"}},
            {"_meta": []},
        ]
        for params in bad:
            with self.subTest(params=params):
                response = self.post(
                    {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params}, headers
                )

                self.assertEqual(400, response.status_code)
                self.assertEqual(-32602, response.json()["error"]["code"])

    def test_discover_without_meta_is_invalid_params(self) -> None:
        response = self.post(
            {"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
            {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "server/discover"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_legacy_request_without_meta_still_works(self) -> None:
        self.assertEqual(200, self.legacy("tools/list").status_code)

    def test_ping_is_legacy_only(self) -> None:
        modern = self.modern("ping")

        self.assertEqual(404, modern.status_code)
        self.assertEqual(-32601, modern.json()["error"]["code"])
        self.assertEqual({}, self.legacy("ping").json()["result"])

    def test_null_id_is_invalid_request(self) -> None:
        response = self.post({"jsonrpc": "2.0", "id": None, "method": "ping"})

        self.assertEqual(-32600, response.json()["error"]["code"])

    def test_request_state_must_be_a_string(self) -> None:
        body = modern_body("tools/call", {"name": "whoami", "arguments": {}, "requestState": 5})

        response = self.post(body, modern_headers(body))

        self.assertEqual(400, response.status_code)
        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_input_responses_must_be_an_object(self) -> None:
        params = {"name": "whoami", "arguments": {}, "inputResponses": ["confirm"]}
        body = modern_body("tools/call", params)

        response = self.post(body, modern_headers(body))

        self.assertEqual(400, response.status_code)
        self.assertEqual(-32602, response.json()["error"]["code"])

    def test_protocol_errors_are_audited_as_such(self) -> None:
        bodies = [
            "{nope",
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": None, "method": "ping"},
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertLogs("server.mcp", "INFO") as logs:
                self.post(body)

                self.assertEqual(
                    "protocol_error", json.loads(logs.records[0].getMessage())["outcome"]
                )
        body = modern_body("tools/list")
        with self.assertLogs("server.mcp", "INFO") as logs:
            self.post(body, {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "other"})
        self.assertEqual("protocol_error", json.loads(logs.records[0].getMessage())["outcome"])

    def test_instructions_make_no_false_claims(self) -> None:
        self.assertIn("never instructions", protocol.INSTRUCTIONS)
        self.assertLess(len(protocol.INSTRUCTIONS), 4096)


class TestTransport(McpProtocolTestCase):
    def test_bad_json_is_parse_error(self) -> None:
        response = self.post("{nope")

        self.assertEqual(400, response.status_code)
        self.assertEqual(-32700, response.json()["error"]["code"])

    def test_batch_is_invalid_request(self) -> None:
        response = self.post([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])

        self.assertEqual(-32600, response.json()["error"]["code"])

    def test_get_and_delete_are_405(self) -> None:
        for method in (self.client.get, self.client.delete):
            response = method("/mcp")

            self.assertEqual(405, response.status_code)
            self.assertEqual("POST", response["Allow"])

    def test_origin(self) -> None:
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        for origin, status in [
            ("https://evil.example", 403),
            ("https://claude.ai", 200),
            ("http://localhost:6274", 200),
            (None, 200),
        ]:
            with self.subTest(origin=origin):
                headers = {"Origin": origin} if origin else {}

                self.assertEqual(status, self.post(ping, headers).status_code)

    def test_responses_are_json(self) -> None:
        response = self.modern("tools/list")

        self.assertEqual("application/json", response["Content-Type"])
        self.assertNotIn("Mcp-Session-Id", response)


class TestAudiences(McpProtocolTestCase):
    def listed(self, audience: Audience) -> bool:
        registry.TOOLS.pop("probe", None)
        self.add_tool("probe", audience=audience)
        return "probe" in self.names(self.modern("tools/list"))

    def assert_gate(self, audience: Audience, grant: Callable[[], object]) -> None:
        self.assertFalse(self.listed(audience))
        grant()
        self.assertTrue(self.listed(audience))

    def test_captain(self) -> None:
        def grant() -> None:
            player = Player.objects.create(user=self.user, date_of_birth="1990-01-01", gender="F")
            event = create_event("Nationals")
            team = Team.objects.create(name="Pune")
            Registration.objects.create(event=event, team=team, player=player, role="CAP")

        self.assert_gate(Audience.CAPTAIN, grant)

    def test_a_default_role_registration_is_not_a_captain(self) -> None:
        player = Player.objects.create(user=self.user, date_of_birth="1990-01-01", gender="F")
        Registration.objects.create(
            event=create_event("Nationals"), team=Team.objects.create(name="Pune"), player=player
        )

        self.assertFalse(self.listed(Audience.CAPTAIN))

    def test_uc_captain(self) -> None:
        def grant() -> None:
            person = UCPerson.objects.create(email="a@x.com", slug="asha")
            Player.objects.create(
                user=self.user,
                date_of_birth="1990-01-01",
                gender="F",
                ultimate_central_id=person.pk,
            )
            UCRegistration.objects.create(
                event=create_event("Nationals"),
                team=Team.objects.create(name="Pune"),
                person=person,
                roles=["player", "captain"],
            )

        self.assert_gate(Audience.CAPTAIN, grant)

    def test_team_admin_is_a_captain(self) -> None:
        self.assert_gate(
            Audience.CAPTAIN, lambda: Team.objects.create(name="Pune").admins.add(self.user)
        )

    def test_handler(self) -> None:
        def grant() -> None:
            committee = Committee.objects.create(name="Welfare", slug="welfare")
            CommitteeRole.objects.create(
                committee=committee, user=self.user, title="Member", start_date="2020-01-01"
            )

        self.assert_gate(Audience.HANDLER, grant)

    def test_staff_is_a_handler(self) -> None:
        self.assert_gate(
            Audience.HANDLER, lambda: User.objects.filter(pk=self.user.pk).update(is_staff=True)
        )

    def test_poster(self) -> None:
        def grant() -> None:
            committee = Committee.objects.create(
                name="Comms", slug="comms", can_post_announcements=True
            )
            CommitteeRole.objects.create(
                committee=committee, user=self.user, title="Member", start_date="2020-01-01"
            )

        self.assert_gate(Audience.POSTER, grant)

    def director_grant(self) -> None:
        Tournament.objects.create(event=create_event("Nationals")).directors.add(self.user)

    def test_director(self) -> None:
        self.assert_gate(Audience.DIRECTOR, self.director_grant)

    @override_settings(TOURNAMENT_AGENT_ENABLED=False)
    def test_director_needs_the_agent_flag(self) -> None:
        self.director_grant()

        self.assertFalse(self.listed(Audience.DIRECTOR))

    def test_account_viewer(self) -> None:
        self.assert_gate(
            Audience.ACCOUNT_VIEWER,
            lambda: PaymentAccount.objects.create(name="Main", slug="main").viewers.add(self.user),
        )

    def test_developer(self) -> None:
        self.assert_gate(
            Audience.DEVELOPER,
            lambda: User.objects.filter(pk=self.user.pk).update(is_superuser=True),
        )

    def test_a_hidden_audience_tool_cannot_be_called(self) -> None:
        self.add_tool("probe", audience=Audience.DIRECTOR)

        response = self.modern("tools/call", {"name": "probe", "arguments": {}})

        self.assertEqual(-32602, response.json()["error"]["code"])
