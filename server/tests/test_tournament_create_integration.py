"""The new-tournament form sends the tags the server expects."""

import datetime
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.tournament.models import Event
from server.utils import today

TAGS = {
    "is_iu_sanctioned": "true",
    "is_subscription_needed": "true",
    "age": "U24",
    "surface": "Beach",
    "level": "College",
    "stage": "Regionals",
    "format": "5v5",
    "skill_division": "Not split",
    "is_adaptive": "false",
}
MEMBERSHIP_RULE = "Needs IU membership, so it must be sanctioned by India Ultimate."


@pytest.mark.django_db(transaction=True)
class TestTournamentCreateIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def open_form(self) -> None:
        staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True, phone="+919999999999"
        )
        self.sign_in_as(staff)
        self.open(f"{APP_URL}/tournament-manager")
        self.wait_for_element("select#surface", timeout=5)

    def fill(self, name: str, value: str) -> None:
        # As a keyboard user does: focus the field, then change it. (Date
        # inputs don't take typed text the same way in every browser.)
        self.execute_script(
            "const el = document.getElementById(arguments[0]);"
            "el.focus();"
            "el.value = arguments[1];"
            "el.dispatchEvent(new Event('input', {bubbles: true}));"
            "el.dispatchEvent(new Event('change', {bubbles: true}));",
            name,
            value,
        )

    def fill_details(self) -> None:
        def day(n: int) -> str:
            return (today() + datetime.timedelta(days=n)).isoformat()

        for name, value in {
            "title": "Tagged Open",
            "start_date": day(60),
            "end_date": day(61),
            "team_registration_start_date": day(1),
            "team_registration_end_date": day(10),
            "team_partial_registration_end_date": day(5),
            "team_late_penalty_end_date": day(12),
            "player_registration_start_date": day(11),
            "player_registration_end_date": day(20),
            "player_late_penalty_end_date": day(22),
            "location": "Goa",
            "team_fee": "0",
            "partial_team_fee": "0",
            "team_late_penalty": "0",
            "player_fee": "0",
            "player_late_penalty": "0",
            "type": "OPN",
        }.items():
            self.fill(name, value)

    def test_the_form_saves_the_tags(self) -> None:
        self.open_form()
        self.fill_details()
        for name, value in TAGS.items():
            self.fill(name, value)
        self.click('button[type="submit"]:contains("Submit")')

        self.wait_for_text("Created Tournament!", timeout=10)
        event = Event.objects.get(title="Tagged Open")
        self.assertEqual(
            (True, "U24", "Beach", "College", "Regionals", "5v5", None, False),
            tuple(getattr(event, field) for field in Event.TAG_FIELDS),
        )
        self.assertTrue(event.is_subscription_needed)

    def test_membership_needs_sanctioned_in_the_form(self) -> None:
        self.open_form()
        self.fill_details()
        for name, value in {**TAGS, "is_iu_sanctioned": "false"}.items():
            self.fill(name, value)
        self.click('button[type="submit"]:contains("Submit")')
        self.assert_text(MEMBERSHIP_RULE)
        self.assertFalse(Event.objects.filter(title="Tagged Open").exists())
        self.fill("is_subscription_needed", "false")
        self.assert_text_not_visible(MEMBERSHIP_RULE)

    def test_changing_membership_keeps_focus_and_checks_live(self) -> None:
        self.open_form()
        self.fill("is_iu_sanctioned", "false")
        self.fill("is_subscription_needed", "true")
        self.assert_text(MEMBERSHIP_RULE)
        self.assertEqual(
            "is_subscription_needed", self.execute_script("return document.activeElement.id")
        )
