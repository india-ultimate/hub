"""An admin told about a likely copy of their team, merging it in one click."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.duplicates.teams.models import TeamNotDuplicate
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server


@pytest.mark.django_db(transaction=True)
class TestTeamDuplicatesIntegration(BaseCase):
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
        self.copy = Team.objects.create(name="goose bumps")
        self.kept.admins.add(self.captain)
        self.copy.admins.add(self.captain)

    def test_the_dashboard_leads_to_a_one_click_merge(self) -> None:
        self.sign_in_as(self.captain)
        self.open(f"{APP_URL}/dashboard")
        self.assert_text("may have been added twice", "#duplicate-teams-notice")
        self.click("#duplicate-teams-notice a")
        # The copy arrives ticked, so the merge is the only thing left to do.
        self.assert_element(f'input[name="keeper"][value="{self.kept.pk}"]')
        self.click("#team-merge-submit")
        self.assert_element("#team-merge-done")
        self.assertFalse(Team.objects.filter(pk=self.copy.pk).exists())

    def test_not_a_copy_stops_the_suggestion(self) -> None:
        self.sign_in_as(self.captain)
        self.open(f"{APP_URL}/team/{self.kept.slug}/merge")
        self.click('button:contains("Not a copy")')
        self.assert_text("We won't suggest")
        self.assertTrue(TeamNotDuplicate.objects.filter(team=self.kept, other=self.copy).exists())
        self.open(f"{APP_URL}/dashboard")
        self.assert_element_absent("#duplicate-teams-notice")
