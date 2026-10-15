"""Managing help categories in the Hub, and a player's new-ticket form."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.committee.models import Committee, TicketRoute
from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.ticket.models import Ticket, TicketCategory


@pytest.mark.django_db(transaction=True)
class TestTicketCategoriesIntegration(BaseCase):
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
        self.player = User.objects.create_user("player@example.com", "player@example.com", "pw")
        # A transactional test database is emptied, seed rows included
        for order, key in enumerate(["Account", "Competitions", "Tech", "Payment"]):
            TicketCategory.objects.get_or_create(key=key, defaults={"name": key, "order": order})
        self.zonal = Committee.objects.create(name="Zonal", slug="zonal", order=99)

    def test_staff_add_rename_route_and_retire_a_category(self) -> None:
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/tickets/manage")
        self.type("#new-category", "Umpiring")
        self.click('button:contains("Add")')
        self.wait_for_element("#name-umpiring", timeout=10)

        self.type("#name-umpiring", "Rules and umpiring\n")
        self.wait_for_element('[aria-label="Move Rules and umpiring up"]', timeout=5)
        category = TicketCategory.objects.get(key="umpiring")
        self.assertEqual(category.name, "Rules and umpiring")

        self.select_option_by_text('[aria-label="Add a committee to Rules and umpiring"]', "Zonal")
        self.wait_for_element('[aria-label="Remove Zonal from Rules and umpiring"]', timeout=5)
        self.assertTrue(
            TicketRoute.objects.filter(category=category, committee=self.zonal).exists()
        )

        self.click('button:contains("Retire Rules and umpiring")')
        self.wait_for_text("Retired (1)", timeout=5)
        category.refresh_from_db()
        self.assertTrue(category.is_retired)

    def test_a_retired_category_leaves_the_new_ticket_form(self) -> None:
        TicketCategory.objects.filter(key="Tech").update(is_retired=True)
        self.sign_in_as(self.player)
        self.open(f"{APP_URL}/tickets/new")
        self.wait_for_element("#category option[value='Payment']", timeout=10)
        self.assert_element_absent("#category option[value='Tech']")

    def test_staff_reorder_and_restore_categories(self) -> None:
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/tickets/manage")
        self.click('[aria-label="Move Competitions up"]')
        self.wait_for_element('[aria-label="Move Account down"]:not([disabled])', timeout=5)
        names = list(TicketCategory.objects.filter(is_retired=False).order_by("order", "name"))
        self.assertEqual([c.key for c in names[:2]], ["Competitions", "Account"])

        self.click('button:contains("Retire Tech")')
        self.wait_for_text("Retired (1)", timeout=5)
        self.click("summary")
        self.click('button:contains("Restore Tech")')
        self.wait_for_element('[aria-label="Move Tech up"]', timeout=5)
        self.assertFalse(TicketCategory.objects.get(key="Tech").is_retired)

    def test_an_old_link_to_a_retired_category_keeps_its_filter(self) -> None:
        TicketCategory.objects.filter(key="Tech").update(is_retired=True)
        Ticket.objects.create(
            title="Site is slow", description="Hangs", created_by=self.player, category_id="Tech"
        )
        self.sign_in_as(self.player)
        self.open(f"{APP_URL}/tickets?category=Tech&status=all")
        self.wait_for_text("Site is slow", timeout=10)
        self.assertEqual(
            self.execute_script(
                "return document.querySelector('#filter-category').selectedOptions[0].textContent"
            ),
            "Tech",
        )

    def test_a_player_cannot_manage_categories(self) -> None:
        self.sign_in_as(self.player)
        self.open(f"{APP_URL}/tickets")
        self.wait_for_element('a[href="/tickets/new"]', timeout=10)
        self.assert_element_absent('a[href="/tickets/manage"]')
        self.open(f"{APP_URL}/tickets/manage")
        self.wait_for_text("Sorry, you do not have access to this page", timeout=10)
