"""The tournament manager's and the transactions page's modals are native
dialogs: each opens, closes (button, Escape) and reopens, and focus goes back to
its trigger. (They were flowbite modals, whose triggers could be bound twice.)"""

import datetime
from contextlib import ExitStack

import pytest
from selenium.webdriver.common.keys import Keys
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Match, Pool, Tournament
from server.transaction.models import ManualTransaction


@pytest.mark.django_db(transaction=True)
class TestDialogsIntegration(BaseCase):
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
        self.staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True, phone="+919999999999"
        )

    def assert_opens_closes_reopens(self, trigger: str, title: str) -> None:
        dialog = f'dialog:contains("{title}")'
        self.assert_element_not_visible(dialog)
        self.click(trigger)
        self.wait_for_element_visible(dialog, timeout=3)
        self.click("dialog[open] button.h-11")
        self.wait_for_element_not_visible(dialog, timeout=3)
        # Closed, focus is back on the button that opened it.
        self.assertTrue(
            self.execute_script(
                "return document.activeElement.textContent.includes(arguments[0])",
                trigger.split('"')[1],
            )
        )
        self.click(trigger)
        self.wait_for_element_visible(dialog, timeout=3)
        self.send_keys("body", Keys.ESCAPE)
        self.wait_for_element_not_visible(dialog, timeout=3)

    def test_the_validation_modal_opens_every_time(self) -> None:
        ManualTransaction.objects.create(
            transaction_id="txn-1", amount=100, currency="INR", user=self.staff
        )
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/validate-transactions")
        self.assert_opens_closes_reopens('button:contains("Validate")', "Validate Transaction")

    def test_the_rules_and_spirit_modals_open_every_time(self) -> None:
        event = open_event(title="Nationals", type="OPN")
        tournament = Tournament.objects.create(event=event, status=Tournament.Status.LIVE)
        one = Team.objects.create(name="Alpha")
        two = Team.objects.create(name="Bravo")
        pool = Pool.objects.create(
            tournament=tournament,
            sequence_number=1,
            name="A",
            initial_seeding={"1": one.id, "2": two.id},
            results={},
        )
        Match.objects.create(
            tournament=tournament,
            pool=pool,
            sequence_number=1,
            status=Match.Status.COMPLETED,
            time=datetime.datetime.now(datetime.UTC),
            team_1=one,
            team_2=two,
            placeholder_seed_1=1,
            placeholder_seed_2=2,
        )
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/tournament-manager")
        self.select_option_by_text("select#tournaments", "Nationals")
        self.assert_opens_closes_reopens('button:contains("Edit Format")', "Rules Editor")
        self.assert_opens_closes_reopens('button:contains("Add Spirit Score")', "Add Spirit Score")
