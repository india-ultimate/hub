"""A team admin merging duplicate teams from the team's own pages."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.servicerequests.models import ServiceRequest, ServiceRequestType
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server


@pytest.mark.django_db(transaction=True)
class TestTeamMergeIntegration(BaseCase):
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

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        self.captain = User.objects.create_user(
            "captain@example.com", "captain@example.com", "pw", first_name="Asha"
        )
        self.kept = Team.objects.create(name="Goosebumps", city="Bengaluru")
        self.copy = Team.objects.create(name="Goosebumps ")
        self.kept.admins.add(self.captain)

    def pick_the_copy(self) -> None:
        self.sign_in_as(self.captain)
        self.open(f"{APP_URL}/team/{self.kept.slug}/edit")
        self.click('a[href$="/merge"]')
        self.assert_text(f"#{self.copy.pk}")
        self.click(f'//label[contains(., "#{self.copy.pk}")]//input[@type="checkbox"]', by="xpath")
        self.assert_element('input[name="keeper"]')

    def test_an_admin_of_both_merges_them(self) -> None:
        self.copy.admins.add(self.captain)
        Team.objects.filter(pk=self.kept.pk).update(image_url="https://example.com/a.png")
        Team.objects.filter(pk=self.copy.pk).update(image_url="https://example.com/b.png")
        self.pick_the_copy()
        self.click(f'input[name="keeper"][value="{self.kept.pk}"]')
        self.click(f'input[name="logo"][value="{self.copy.pk}"]')
        self.assert_text(f"Merge into Goosebumps #{self.kept.pk}", "#team-merge-submit")
        self.click("#team-merge-submit")
        self.assert_text(f"Merged into Goosebumps #{self.kept.pk}", "#team-merge-done")
        self.assertFalse(Team.objects.filter(pk=self.copy.pk).exists())
        self.kept.refresh_from_db()
        self.assertEqual(self.kept.image_url, "https://example.com/b.png")

    def test_an_admin_of_one_asks_staff(self) -> None:
        self.pick_the_copy()
        # Searching for something else keeps the ticked team in view.
        self.type("#team-merge-search", "Somebody else")
        self.assert_text(f"#{self.copy.pk}")
        self.assert_text("Nothing changes until our staff approve")
        self.assert_text("Send to our staff", "#team-merge-submit")
        self.type("#team-merge-message", "We made the team twice last season")
        self.click("#team-merge-submit")
        self.assert_text("Request sent", "#team-merge-done")
        self.assert_element(f'#team-merge-done a[href="/team/{self.kept.slug}"]')
        asked = ServiceRequest.objects.get(type=ServiceRequestType.REQUEST_TEAM_MERGE)
        self.assertEqual(set(asked.service_teams.all()), {self.kept, self.copy})
        self.assertTrue(Team.objects.filter(pk=self.copy.pk).exists())
