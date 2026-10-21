import csv
import io
import json
from typing import Any

from django.test import Client, TestCase

from server.core.models import User
from server.forms.models import Form, FormResponse

TEST_PASSWORD = "test_password_123"  # nosec B105


class FormsAPITestCase(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password=TEST_PASSWORD,
            phone="9999999999",
            first_name="Staff",
            last_name="User",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password=TEST_PASSWORD,
            phone="8888888888",
            first_name="Member",
            last_name="User",
        )
        self.form = Form.objects.create(
            title="Feedback Form",
            slug="feedback-form",
            description="Tell us what you think",
            fields=[
                {
                    "key": "comments",
                    "label": "Comments",
                    "type": "textarea",
                    "required": True,
                    "options": [],
                },
                {
                    "key": "rating",
                    "label": "Rating",
                    "type": "dropdown",
                    "required": False,
                    "options": ["Good", "Okay", "Bad"],
                },
            ],
            payment_amount=None,
            is_active=True,
            created_by=self.staff,
        )

    def _login(self, user: User) -> None:
        self.client.force_login(user)

    def _payload(self, sections: list[dict[str, Any]], fields: list[dict[str, Any]]) -> Any:
        self._login(self.staff)
        return self.client.post(
            "/api/forms/",
            data=json.dumps({"title": "Sectioned", "sections": sections, "fields": fields}),
            content_type="application/json",
        )

    def test_create_form_with_sections_round_trips(self) -> None:
        sections = [
            {"key": "s1", "title": "One", "description": "", "next": "submit"},
            {"key": "s2", "title": "Two", "description": "", "next": ""},
        ]
        fields = [
            {
                "key": "q",
                "label": "Q",
                "type": "radio",
                "required": True,
                "options": ["Yes", "No"],
                "section": "s1",
                "goto": {"Yes": "s2", "No": ""},
            }
        ]
        response = self._payload(sections, fields)
        self.assertEqual(response.status_code, 200, response.content)
        got = self.client.get(f"/api/forms/{response.json()['slug']}").json()
        self.assertEqual(got["sections"], sections)
        self.assertEqual(got["fields"][0]["goto"], {"Yes": "s2", "No": ""})

    def test_create_legacy_payload_still_works(self) -> None:
        self._login(self.staff)
        response = self.client.post(
            "/api/forms/",
            data=json.dumps(
                {
                    "title": "Old",
                    "fields": [{"key": "a", "label": "A", "type": "text"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sections"], [])

    def test_structure_rejections(self) -> None:
        def sec(key: str, nxt: str = "") -> dict[str, Any]:
            return {"key": key, "title": "", "description": "", "next": nxt}

        def fld(
            section: str = "s1",
            type: str = "radio",
            goto: dict[str, str] | None = None,
            key: str = "q",
        ) -> dict[str, Any]:
            return {
                "key": key,
                "label": key,
                "type": type,
                "options": ["Yes", "No"] if type == "radio" else [],
                "section": section,
                "goto": goto or {},
            }

        two = [sec("s1"), sec("s2")]
        cases = {
            "duplicate key": ([sec("s1"), sec("s1")], [fld()]),
            "empty key": ([sec("")], [fld("")]),
            "unknown field section": (two, [fld("zzz")]),
            "section without sections": ([], [fld("s1")]),
            "goto without sections": ([], [fld("", goto={"Yes": "submit"})]),
            "goto on text": (two, [fld(type="text", goto={"Yes": "s2"})]),
            "goto key not option": (two, [fld(goto={"Maybe": "s2"})]),
            "goto own section": (two, [fld(goto={"Yes": "s1"})]),
            "goto earlier section": (two, [fld("s2", goto={"Yes": "s1"})]),
            "goto unknown": (two, [fld(goto={"Yes": "nope"})]),
            "next backwards": ([sec("s1"), sec("s2", "s1")], [fld("s2")]),
            "two branching in a section": (
                two,
                [fld(goto={"Yes": "s2"}), fld(goto={"No": "s2"}, key="r")],
            ),
        }
        for name, (sections, fields) in cases.items():
            with self.subTest(name):
                response = self._payload(sections, fields)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertTrue(response.json()["message"])

    def test_update_rejects_bad_structure(self) -> None:
        self._login(self.staff)
        sections = [
            {"key": "s1", "title": "", "description": "", "next": ""},
            {"key": "s2", "title": "", "description": "", "next": ""},
        ]
        field = {
            "key": "q",
            "label": "Q",
            "type": "radio",
            "options": ["Yes"],
            "section": "s2",
            "goto": {"Yes": "s1"},
        }
        response = self.client.put(
            f"/api/forms/{self.form.slug}",
            data=json.dumps({"title": "Changed", "sections": sections, "fields": [field]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.form.refresh_from_db()
        self.assertEqual(self.form.title, "Feedback Form")
        self.assertEqual(self.form.sections, [])

    def test_update_form_can_stop_accepting_responses(self) -> None:
        self._login(self.staff)
        payload = {
            "title": self.form.title,
            "description": self.form.description,
            "fields": self.form.fields,
            "payment_amount": None,
            "is_active": False,
        }
        response = self.client.put(
            f"/api/forms/{self.form.slug}",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["is_active"])
        self.form.refresh_from_db()
        self.assertFalse(self.form.is_active)

    def test_submit_rejected_when_form_inactive(self) -> None:
        self.form.is_active = False
        self.form.save(update_fields=["is_active"])
        self._login(self.user)

        response = self.client.post(
            f"/api/forms/{self.form.slug}/responses",
            data=json.dumps({"answers": {"comments": "Hello"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not active", response.json()["message"])
        self.assertEqual(FormResponse.objects.count(), 0)

    def test_submit_allowed_when_form_active(self) -> None:
        self._login(self.user)
        response = self.client.post(
            f"/api/forms/{self.form.slug}/responses",
            data=json.dumps({"answers": {"comments": "Great event", "rating": "Good"}}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(FormResponse.objects.filter(is_paid=True).count(), 1)

    def _branching_form(self, a_next: str = "", goto: bool = True) -> Form:
        def text(key: str, label: str, section: str) -> dict[str, Any]:
            return {
                "key": key,
                "label": label,
                "type": "text",
                "required": True,
                "options": [],
                "section": section,
            }

        radio: dict[str, Any] = {
            "key": "route",
            "label": "Route",
            "type": "radio",
            "required": False,
            "options": ["Skip", "All"],
            "section": "s_a",
        }
        if goto:
            radio["goto"] = {"Skip": "s_c", "All": ""}
        return Form.objects.create(
            title="Branching",
            slug="branching",
            sections=[
                {"key": "s_a", "title": "A", "description": "", "next": a_next},
                {"key": "s_b", "title": "B", "description": "", "next": ""},
                {"key": "s_c", "title": "C", "description": "", "next": ""},
            ],
            fields=[
                radio,
                text("a", "A field", "s_a"),
                text("b", "B field", "s_b"),
                text("c", "C field", "s_c"),
            ],
            is_active=True,
            created_by=self.staff,
        )

    def _submit(self, form: Form, answers: dict[str, Any]) -> Any:
        self._login(self.user)
        return self.client.post(
            f"/api/forms/{form.slug}/responses",
            data=json.dumps({"answers": answers}),
            content_type="application/json",
        )

    def test_branch_skips_required_section(self) -> None:
        form = self._branching_form()
        response = self._submit(form, {"route": "Skip", "a": "1", "c": "3"})
        self.assertEqual(response.status_code, 200)

    def test_branch_on_path_still_required(self) -> None:
        form = self._branching_form()
        response = self._submit(form, {"route": "All", "a": "1", "c": "3"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("B field", response.json()["message"])

    def test_abandoned_branch_answers_not_stored(self) -> None:
        form = self._branching_form()
        self._submit(form, {"route": "Skip", "a": "1", "b": "2", "c": "3"})
        self.assertEqual(set(FormResponse.objects.get().answers), {"route", "a", "c"})

    def test_unanswered_optional_branch_falls_through(self) -> None:
        form = self._branching_form()
        response = self._submit(form, {"a": "1", "c": "3"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("B field", response.json()["message"])

    def test_section_next_submit_ends_form(self) -> None:
        form = self._branching_form(a_next="submit", goto=False)
        response = self._submit(form, {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FormResponse.objects.get().answers, {"a": "1"})

    def test_legacy_form_unchanged(self) -> None:
        self.assertEqual(self._submit(self.form, {"rating": "Good"}).status_code, 400)
        response = self._submit(self.form, {"comments": "Hi", "rating": "Good"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FormResponse.objects.get().answers, {"comments": "Hi", "rating": "Good"})

    def test_unknown_answer_keys_not_stored(self) -> None:
        self._submit(self.form, {"comments": "Hi", "extra": "x"})
        self.assertEqual(FormResponse.objects.get().answers, {"comments": "Hi"})

    def test_non_string_branch_answer_is_invalid_choice(self) -> None:
        form = self._branching_form()
        response = self._submit(form, {"route": ["Skip"], "a": "1", "b": "2", "c": "3"})
        self.assertEqual(response.status_code, 400)

    def test_inactive_forms_hidden_from_non_staff_list(self) -> None:
        self.form.is_active = False
        self.form.save(update_fields=["is_active"])

        self._login(self.user)
        response = self.client.get("/api/forms/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        self._login(self.staff)
        response = self.client.get("/api/forms/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertFalse(response.json()[0]["is_active"])

    def test_export_responses_csv(self) -> None:
        FormResponse.objects.create(
            form=self.form,
            user=self.user,
            answers={"comments": "Loved it", "rating": "Good"},
            is_paid=True,
        )
        FormResponse.objects.create(
            form=self.form,
            user=self.user,
            answers={"comments": "Needs work", "rating": ["Okay", "Bad"]},
            is_paid=True,
        )
        # Unpaid responses must not appear in the export.
        FormResponse.objects.create(
            form=self.form,
            user=self.user,
            answers={"comments": "draft"},
            is_paid=False,
        )

        self._login(self.staff)
        response = self.client.get(f"/api/forms/{self.form.slug}/responses/csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("feedback-form-responses.csv", response["Content-Disposition"])

        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["Name", "Email", "Phone", "Submitted", "Comments", "Rating"])
        self.assertEqual(len(rows), 3)  # header + 2 paid responses
        # Newest first
        self.assertEqual(rows[1][0], "Member User")
        self.assertEqual(rows[1][1], "member@example.com")
        self.assertEqual(rows[1][2], "8888888888")
        self.assertEqual(rows[1][4], "Needs work")
        self.assertEqual(rows[1][5], "Okay, Bad")
        self.assertEqual(rows[2][4], "Loved it")
        self.assertEqual(rows[2][5], "Good")

    def test_export_responses_csv_requires_staff(self) -> None:
        self._login(self.user)
        response = self.client.get(f"/api/forms/{self.form.slug}/responses/csv")
        self.assertEqual(response.status_code, 401)
