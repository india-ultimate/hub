import csv
import io
import json

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
