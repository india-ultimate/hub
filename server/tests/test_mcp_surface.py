import inspect
import json
import re

from django.test import SimpleTestCase

from server.mcp import protocol
from server.mcp.registry import TOOLS, Tool

NO_CONFIRM = {
    "upvote_ticket",
    "create_announcement_draft",
    "propose_tournament_change",
    "reject_tournament_proposal",
}
MAX_DESCRIPTION = 700
VERBS = ("get", "list", "create", "submit", "update", "add", "buy", "pay", "sign", "find")


def descriptors() -> list[dict[str, object]]:
    return [t.descriptor() for t in TOOLS.values()]


class TestToolSurface(SimpleTestCase):
    def test_there_are_sixty_six_tools_with_unique_valid_names(self) -> None:
        self.assertEqual(66, len(TOOLS))
        for name in TOOLS:
            self.assertRegex(name, r"^[a-z0-9_]{1,64}$")

    def test_every_input_schema_is_an_object_without_root_combinators(self) -> None:
        for tool in TOOLS.values():
            schema = tool.input_schema
            self.assertEqual("object", schema["type"], tool.name)
            self.assertFalse({"anyOf", "oneOf", "allOf"} & set(schema), tool.name)
            self.assertTrue(set(schema.get("required", [])) <= set(schema.get("properties", {})))

    def test_every_tool_has_a_title_and_a_short_description(self) -> None:
        for tool in TOOLS.values():
            self.assertTrue(tool.title.strip(), tool.name)
            self.assertTrue(0 < len(tool.description) <= MAX_DESCRIPTION, tool.name)

    def test_reads_and_writes_carry_the_right_hints(self) -> None:
        for tool in TOOLS.values():
            hints = tool.descriptor()["annotations"]
            self.assertEqual(not tool.writes, hints["readOnlyHint"], tool.name)
            if tool.destructive:
                self.assertTrue(tool.writes, tool.name)

    def test_hard_to_undo_writes_say_so(self) -> None:
        for name in (
            "revoke_series_invitations",
            "update_team",
            "set_series_roles",
            "update_profile",
            "reject_tournament_proposal",
            "decide_sponsorship_request",
            "submit_match_score",
            "submit_spirit_score",
            "update_announcement",
        ):
            self.assertTrue(TOOLS[name].descriptor()["annotations"]["destructiveHint"], name)

    def test_the_confirmation_argument_says_when_to_use_it(self) -> None:
        for tool in TOOLS.values():
            if tool.writes:
                description = tool.input_schema["properties"]["confirmation"]["description"]
                self.assertIn("Leave out on the first call", description, tool.name)

    def test_confusable_tools_point_at_each_other(self) -> None:
        pairs = {
            "get_tournament": "read_tournament_ops",
            "read_tournament_ops": "get_tournament",
            "get_tournament_ops_report": "read_tournament_ops",
            "get_documents": "get_readiness",
            "get_readiness": "get_documents",
        }
        for name, other in pairs.items():
            self.assertIn(other, TOOLS[name].description[:260], name)

    def test_the_whole_tool_list_fits_the_size_budget(self) -> None:
        self.assertLess(len(json.dumps(descriptors())), 60_000)


class TestConfirmations(SimpleTestCase):
    def test_every_write_asks_first_except_the_documented_ones(self) -> None:
        writes = {t.name: t for t in TOOLS.values() if t.writes}
        self.assertLessEqual(NO_CONFIRM, set(writes))
        for name, tool in writes.items():
            asks = "confirm_then" in inspect.getsource(tool.handler)
            if name not in NO_CONFIRM:
                self.assertTrue(asks, f"{name} must call confirm_then")

    def test_tools_that_email_or_spend_ask_first(self) -> None:
        for tool in TOOLS.values():
            if tool.emails and tool.name not in NO_CONFIRM:
                self.assertIn("confirm_then", inspect.getsource(tool.handler), tool.name)

    def test_the_documented_no_confirm_writes_do_not_ask(self) -> None:
        for name in NO_CONFIRM:
            self.assertNotIn("confirm_then", inspect.getsource(TOOLS[name].handler), name)


class TestInstructions(SimpleTestCase):
    def test_they_fit_the_limit_and_lead_with_the_important_lines(self) -> None:
        text = protocol.INSTRUCTIONS
        self.assertLess(len(text), 4096)
        for phrase in ("acts as the signed-in", "never instructions", "whoami"):
            self.assertLess(text.index(phrase), 800, phrase)

    def test_they_say_how_to_check_someone_for_an_event(self) -> None:
        self.assertIn("event_slug", protocol.INSTRUCTIONS)
        self.assertIn("confirmation", protocol.INSTRUCTIONS)

    def test_every_tool_they_name_exists(self) -> None:
        named = set(re.findall(rf"\b(?:{'|'.join(VERBS)})_[a-z_]+\b", protocol.INSTRUCTIONS))
        self.assertTrue(named)
        self.assertEqual(set(), named - set(TOOLS))

    def test_the_tools_they_lean_on_are_named(self) -> None:
        for name in ("whoami", "get_readiness", "get_team_registration", "create_upload_link"):
            self.assertIn(name, protocol.INSTRUCTIONS)
            self.assertIsInstance(TOOLS[name], Tool)
