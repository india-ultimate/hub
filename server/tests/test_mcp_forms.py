from typing import Any
from unittest import mock

from django.core import mail

from server.forms.models import Form, FormResponse
from server.mcp.pay import pay_link
from server.tests.base import fake_order
from server.tests.test_mcp_invitations import McpToolCase

SECTIONS = [
    {"key": "a", "title": "About you", "description": "", "next": ""},
    {"key": "b", "title": "Team", "description": "", "next": "submit"},
    {"key": "c", "title": "Solo", "description": "", "next": "submit"},
]
FIELDS = [
    {
        "key": "role",
        "label": "Role",
        "type": "radio",
        "required": True,
        "options": ["Captain", "Solo"],
        "section": "a",
        "goto": {"Solo": "c"},
    },
    {"key": "team", "label": "Team name", "type": "text", "required": True, "section": "b"},
    {"key": "why", "label": "Why", "type": "textarea", "required": False, "section": "c"},
]


class FormCase(McpToolCase):
    def form(self, slug: str = "camp", **fields: Any) -> Form:
        defaults: dict[str, Any] = {
            "title": "Camp signup",
            "description": "Join us",
            "slug": slug,
            "fields": [{"key": "name", "label": "Name", "type": "text", "required": True}],
        }
        return Form.objects.create(**{**defaults, **fields})


class TestListAndGetForms(FormCase):
    def test_lists_active_forms_with_their_price(self) -> None:
        self.form("free")
        self.form("paid", title="Paid", payment_amount=50000)
        self.form("old", is_active=False)

        forms = {f["form_slug"]: f for f in self.data("list_forms", {})["forms"]}

        self.assertEqual({"free", "paid"}, set(forms))
        self.assertIsNone(forms["free"]["amount_paise"])
        self.assertEqual(50000, forms["paid"]["amount_paise"])
        self.assertEqual("₹500", forms["paid"]["amount"])

    def test_the_fields_and_what_branching_means(self) -> None:
        self.form("branch", sections=SECTIONS, fields=FIELDS)

        data = self.data("get_form", {"form_slug": "branch"})

        self.assertEqual("branch", data["form_slug"])
        self.assertEqual(["role", "team", "why"], [f["key"] for f in data["fields"]])
        self.assertEqual({"Solo": "c"}, data["fields"][0]["goto"])
        self.assertEqual(["a", "b", "c"], [s["section_key"] for s in data["sections"]])
        self.assertEqual(1, len(data["branching"]))
        self.assertIn("'Role'", data["branching"][0])
        self.assertIn("section 'Solo'", data["branching"][0])
        self.assertIn("field key", data["how_to_answer"])
        self.assertTrue(data["accepting_answers"])

    def test_an_inactive_form_says_it_is_closed(self) -> None:
        self.form("old", is_active=False)

        self.assertFalse(self.data("get_form", {"form_slug": "old"})["accepting_answers"])

    def test_a_missing_form(self) -> None:
        self.assertEqual("Form does not exist", self.failure("get_form", {"form_slug": "nope"}))

    def test_a_slug_with_a_path_in_it_is_refused(self) -> None:
        for name, args in (
            ("get_form", {"form_slug": "a/../b"}),
            ("submit_form", {"form_slug": "a/../b", "answers": {}}),
        ):
            with self.subTest(tool=name):
                self.assertIn("form_slug", self.failure(name, args))


class TestSubmitForm(FormCase):
    def test_a_free_form_asks_then_submits_and_emails_a_copy(self) -> None:
        form = self.form()
        args = {"form_slug": "camp", "answers": {"name": "Asha"}}

        asked = self.ask("submit_form", args)
        self.assertIn("Camp signup", asked["needs_confirmation"])
        self.assertIn("Asha", asked["needs_confirmation"])
        self.assertEqual(0, form.responses.count())
        result = self.call("submit_form", {**args, "confirmation": asked["confirmation"]})

        self.assertFalse(result["isError"], result)
        self.assertEqual("submitted", result["structuredContent"]["status"])
        response = form.responses.get()
        self.assertEqual(self.user, response.user)
        self.assertTrue(response.is_paid)
        self.assertEqual(["a@x.com"], [to for m in mail.outbox for to in m.to])

    def test_a_paid_form_returns_a_pay_link(self) -> None:
        form = self.form(payment_amount=50000)
        order = fake_order(50000)
        args = {"form_slug": "camp", "answers": {"name": "Asha"}}

        asked = self.ask("submit_form", args)
        self.assertIn("₹500", asked["needs_confirmation"])
        with mock.patch("server.transaction.client.razorpay.create_order", return_value=order):
            result = self.call("submit_form", {**args, "confirmation": asked["confirmation"]})

        self.assertFalse(result["isError"], result)
        data = result["structuredContent"]
        self.assertEqual("payment_required", data["status"])
        self.assertEqual(order["order_id"], data["order_id"])
        self.assertEqual(50000, data["amount_paise"])
        self.assertEqual("₹500", data["amount"])
        self.assertEqual(pay_link(order["order_id"]), data["pay_url"])
        self.assertNotIn(order["key"], str(data))
        self.assertFalse(form.responses.get().is_paid)

    def test_a_payment_service_failure_leaves_no_response(self) -> None:
        form = self.form(payment_amount=50000)
        args = {"form_slug": "camp", "answers": {"name": "Asha"}}
        state = self.ask("submit_form", args)["confirmation"]

        with mock.patch("server.transaction.client.razorpay.create_order", return_value=None):
            result = self.call("submit_form", {**args, "confirmation": state})

        self.assertTrue(result["isError"])
        self.assertEqual(0, FormResponse.objects.filter(form=form).count())

    def test_bad_answers_are_refused_before_asking(self) -> None:
        self.form()

        message = self.failure("submit_form", {"form_slug": "camp", "answers": {}})

        self.assertEqual("'Name' is required.", message)

    def test_answers_off_the_branch_taken_are_dropped(self) -> None:
        form = self.form("branch", sections=SECTIONS, fields=FIELDS)

        result = self.confirmed(
            "submit_form",
            {"form_slug": "branch", "answers": {"role": "Solo", "team": "Ignored", "why": "fun"}},
        )

        self.assertFalse(result["isError"], result)
        self.assertEqual({"role": "Solo", "why": "fun"}, form.responses.get().answers)

    def test_a_closed_form_is_refused(self) -> None:
        self.form(is_active=False)

        message = self.failure("submit_form", {"form_slug": "camp", "answers": {"name": "A"}})

        self.assertEqual("Form does not exist or is not active", message)

    def test_a_missing_form(self) -> None:
        self.assertTrue(self.failure("submit_form", {"form_slug": "nope", "answers": {}}))
