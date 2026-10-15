"""The committees pages: the public directory, the staff page, and the ticket's assignees."""

import datetime
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.committee.models import Committee, Role, TicketRoute
from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.ticket.models import Ticket
from server.utils import today


@pytest.mark.django_db(transaction=True)
class TestCommitteesIntegration(BaseCase):
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
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )
        self.asha = User.objects.create_user(
            "asha@example.com", "asha@example.com", "pw", first_name="Asha", last_name="Singh"
        )
        self.meera = User.objects.create_user(
            "meera@example.com", "meera@example.com", "pw", first_name="Meera", last_name="Rao"
        )
        self.board = Committee.objects.get_or_create(
            slug="executive-board", defaults={"name": "Executive Board"}
        )[0]
        self.zonal = Committee.objects.create(name="Zonal", slug="zonal", order=99)

    def hold(self, committee: Committee, user: User, title: str, is_chair: bool = False) -> Role:
        return Role.objects.create(
            committee=committee,
            user=user,
            title=title,
            is_chair=is_chair,
            start_date=today() - datetime.timedelta(days=30),
        )

    def test_the_public_page_shows_the_board_and_a_committee_with_its_chair(self) -> None:
        self.hold(self.board, self.asha, "President")
        self.hold(self.zonal, self.meera, "Chair", is_chair=True)
        self.open(f"{APP_URL}/committees")
        self.wait_for_text("The people who run India Ultimate.", timeout=10)
        self.assert_text("Asha Singh", "#executive-board + ul")
        self.assert_text("President", "#executive-board + ul")
        card = '[aria-labelledby="committee-zonal"]'
        self.wait_for_element(card, timeout=5)
        self.assert_text("Meera Rao", card)
        self.assert_text("Chair", card)

    def test_staff_add_a_person_and_end_their_term(self) -> None:
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/committees/manage")
        self.wait_for_element("#people-committee", timeout=10)
        self.select_option_by_text("#people-committee", "Zonal")

        self.click('button:contains("Add person")')
        self.type("dialog[open] #person-search", "Asha")
        self.click('dialog[open] button:contains("Asha Singh")')
        self.type("dialog[open] #role-title", "Secretary")
        self.click('dialog[open] button[type="submit"]')
        self.wait_for_text("Saved", timeout=5)
        role = Role.objects.get(committee=self.zonal, user=self.asha)
        self.assertEqual(role.title, "Secretary")
        self.assertIsNone(role.end_date)

        self.click('button[aria-label="End term for Asha Singh"]')
        self.click('dialog[open] button[type="submit"]')
        self.wait_for_element_absent('button[aria-label="End term for Asha Singh"]', timeout=5)
        role.refresh_from_db()
        self.assertEqual(role.end_date, today())

    def test_a_handler_adds_and_removes_an_assignee(self) -> None:
        self.hold(self.zonal, self.meera, "Chair", is_chair=True)
        ticket = Ticket.objects.create(
            title="Cannot pay", description="Card fails", created_by=self.asha
        )
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/tickets/{ticket.id}")
        self.click("#add-assignee")
        self.type("#assignee-search", "Mee")
        self.click('[role="option"]:contains("Meera Rao")')
        self.wait_for_element('button[aria-label="Remove Meera Rao"]', timeout=5)
        self.assertEqual(list(ticket.assignees.all()), [self.meera])

        self.click('button[aria-label="Remove Meera Rao"]')
        self.wait_for_element_absent('button[aria-label="Remove Meera Rao"]', timeout=5)
        self.assertFalse(ticket.assignees.exists())

    def test_staff_create_a_committee_and_it_appears_on_the_public_page(self) -> None:
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/committees/manage")
        self.click("#committees-tab")
        self.type("#new-name", "Umpiring")
        self.type("#new-email", "umpires@example.com")
        self.click('button:contains("Add committee")')
        self.wait_for_text("Saved", timeout=5)
        self.assertTrue(Committee.objects.filter(name="Umpiring").exists())
        self.open(f"{APP_URL}/committees")
        self.wait_for_text("Umpiring", timeout=10)
        self.assert_text("umpires@example.com")

    def test_a_chair_handles_a_routed_ticket_but_cannot_change_its_privacy(self) -> None:
        self.hold(self.zonal, self.meera, "Chair", is_chair=True)
        TicketRoute.objects.create(category=Ticket.Category.TECH, committee=self.zonal)
        ticket = Ticket.objects.create(
            title="Site is slow",
            description="Pages hang",
            created_by=self.asha,
            category=Ticket.Category.TECH,
        )
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/tickets/{ticket.id}")
        self.wait_for_element("#ticket-status", timeout=10)
        self.assert_element("#add-assignee")
        self.assert_element_absent("#privacy-switch")
