import json
from importlib import import_module
from typing import Any
from unittest import mock

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from server.committee.models import Committee, TicketRoute
from server.core.models import User
from server.ticket.models import Ticket, TicketCategory


class CategoryTestCase(TestCase):
    def setUp(self) -> None:
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.player = User.objects.create_user(username="player")

    def call(self, method: str, path: str, user: User, data: dict[str, Any] | None = None) -> Any:
        client = Client()
        client.force_login(user)
        if method == "get":
            return client.get(f"/api/ticket{path}")
        return getattr(client, method)(
            f"/api/ticket{path}", data=json.dumps(data or {}), content_type="application/json"
        )

    def keys(self, user: User, query: str = "") -> list[str]:
        response = self.call("get", f"/categories{query}", user)
        self.assertEqual(200, response.status_code)
        return [category["key"] for category in response.json()]


class TestMigration(CategoryTestCase):
    def test_it_seeds_the_seven_categories_in_order(self) -> None:
        self.assertEqual(
            ["Account", "Competitions", "Subscription", "Tournament", "Payment", "Tech", "Other"],
            list(TicketCategory.objects.values_list("key", flat=True)),
        )
        self.assertEqual(
            list(range(7)), list(TicketCategory.objects.values_list("order", flat=True))
        )

    def test_seeding_again_leaves_every_ticket_as_it_was(self) -> None:
        Ticket.objects.create(
            title="T", description="D", created_by=self.player, category_id="Tech"
        )

        import_module("server.migrations.0176_ticket_categories").seed(apps, None)

        self.assertEqual(7, TicketCategory.objects.count())
        self.assertEqual("Tech", Ticket.objects.get().category_id)


class TestListing(CategoryTestCase):
    def test_active_categories_come_in_order_and_retired_ones_are_hidden(self) -> None:
        TicketCategory.objects.filter(key="Payment").update(is_retired=True)
        TicketCategory.objects.filter(key="Other").update(order=0)

        self.assertEqual(
            ["Account", "Other", "Competitions", "Subscription", "Tournament", "Tech"],
            self.keys(self.player),
        )

    def test_all_adds_the_retired_ones_last_for_staff_only(self) -> None:
        TicketCategory.objects.filter(key="Account").update(is_retired=True)

        self.assertEqual("Account", self.keys(self.staff, "?all=true")[-1])
        self.assertEqual(403, self.call("get", "/categories?all=true", self.player).status_code)


class TestWriting(CategoryTestCase):
    def test_only_staff_may_write(self) -> None:
        self.assertEqual(
            403, self.call("post", "/categories", self.player, {"name": "X"}).status_code
        )
        self.assertEqual(
            403, self.call("put", "/categories/Tech", self.player, {"name": "X"}).status_code
        )
        self.assertEqual(403, self.call("get", "/routes", self.player).status_code)
        self.assertEqual(
            403, self.call("put", "/routes/Tech", self.player, {"committees": []}).status_code
        )

    def test_staff_add_a_category_last_with_a_key_from_its_name(self) -> None:
        response = self.call("post", "/categories", self.staff, {"name": " Gear & Kit "})

        self.assertEqual(201, response.status_code)
        self.assertEqual(
            {"key": "gear-kit", "name": "Gear & Kit", "order": 7, "is_retired": False},
            response.json(),
        )

    def test_blank_or_duplicate_names_are_refused(self) -> None:
        for name in ("", "  ", "tech", "x" * 101):
            response = self.call("post", "/categories", self.staff, {"name": name})
            self.assertEqual(400, response.status_code, name)
        self.assertEqual(
            400, self.call("put", "/categories/Tech", self.staff, {"name": "Other"}).status_code
        )

    def test_unknown_key_and_out_of_range_order(self) -> None:
        self.assertEqual(
            404, self.call("put", "/categories/nope", self.staff, {"name": "X"}).status_code
        )
        for order in (-1, 32768):
            response = self.call("put", "/categories/Tech", self.staff, {"order": order})
            self.assertEqual(400, response.status_code)

    def test_keys_get_a_number_when_taken(self) -> None:
        TicketCategory.objects.create(key="kit", name="Kit")
        self.assertEqual("kit-2", TicketCategory.new_key("Kit!"))
        TicketCategory.objects.create(key="kit-2", name="Another")
        self.assertEqual("kit-3", TicketCategory.new_key("kit!"))
        self.assertEqual("category", TicketCategory.new_key("!!!"))

    def test_a_rename_shows_on_old_tickets_and_keeps_their_key(self) -> None:
        ticket = Ticket.objects.create(
            title="T", description="D", created_by=self.player, category_id="Payment"
        )

        self.call("put", "/categories/Payment", self.staff, {"name": "Money"})

        detail = self.call("get", f"/{ticket.id}", self.staff).json()
        self.assertEqual(("Payment", "Money"), (detail["category"], detail["category_name"]))
        self.assertEqual("Payment", Ticket.objects.get().category_id)


class TestRetiring(CategoryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ticket = Ticket.objects.create(
            title="T", description="D", created_by=self.player, category_id="Payment"
        )
        self.call("put", "/categories/Payment", self.staff, {"is_retired": True})

    def create(self, category: str) -> Any:
        return self.call(
            "post", "/", self.player, {"title": "T", "description": "D", "category": category}
        )

    def test_it_leaves_the_list_but_stays_on_its_tickets(self) -> None:
        self.assertNotIn("Payment", self.keys(self.player))
        self.assertEqual(
            "Payment", self.call("get", f"/{self.ticket.id}", self.player).json()["category"]
        )
        self.assertEqual(
            "Payment",
            self.call("get", "/?category=Payment", self.player).json()["items"][0]["category"],
        )

    def test_new_tickets_cannot_use_it_or_an_unknown_one(self) -> None:
        self.assertEqual(400, self.create("Payment").status_code)
        self.assertEqual(400, self.create("Nonsense").status_code)
        self.assertEqual(201, self.create("").status_code)

    def test_staff_cannot_move_a_ticket_to_it_but_may_leave_it_there(self) -> None:
        other = Ticket.objects.create(title="O", description="D", created_by=self.player)

        moved = self.call("put", f"/{other.id}", self.staff, {"category": "Payment"})
        kept = self.call("put", f"/{self.ticket.id}", self.staff, {"category": "Payment"})

        self.assertEqual((400, 200), (moved.status_code, kept.status_code))

    def test_restoring_brings_it_back(self) -> None:
        self.call("put", "/categories/Payment", self.staff, {"is_retired": False})

        self.assertIn("Payment", self.keys(self.player))
        self.assertEqual(201, self.create("Payment").status_code)


class TestRouting(CategoryTestCase):
    def test_routes_list_every_category_retired_too_and_keyed_by_key(self) -> None:
        self.call("put", "/categories/Tech", self.staff, {"is_retired": True})
        committee = Committee.objects.get(slug="finance")

        response = self.call("put", "/routes/Tech", self.staff, {"committees": ["finance"]})
        routes = self.call("get", "/routes", self.staff).json()

        self.assertEqual({"category": "Tech", "committees": ["finance"]}, response.json())
        self.assertEqual(7, len(routes))
        self.assertEqual(
            ["Tech"], [r["category"] for r in routes if r["committees"] == ["finance"]]
        )
        self.assertTrue(
            TicketRoute.objects.filter(category__key="Tech", committee=committee).exists()
        )

    def test_an_unknown_category_has_no_route(self) -> None:
        response = self.call("put", "/routes/nope", self.staff, {"committees": []})
        self.assertEqual(404, response.status_code)

    def test_a_new_category_routes_new_tickets_to_its_chairs(self) -> None:
        self.call("post", "/categories", self.staff, {"name": "Kit"})
        self.call("put", "/routes/kit", self.staff, {"committees": ["finance"]})

        self.assertEqual(
            ["finance"],
            list(
                Committee.objects.filter(routes__category__key="kit").values_list("slug", flat=True)
            ),
        )


class TestQueries(CategoryTestCase):
    def listing_queries(self) -> int:
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(200, self.call("get", "/", self.staff).status_code)
        return len(queries)

    def test_the_list_costs_the_same_however_many_categories_the_tickets_have(self) -> None:
        Ticket.objects.create(
            title="A", description="D", created_by=self.player, category_id="Tech"
        )
        before = self.listing_queries()

        for key in ("Account", "Payment", "Other"):
            Ticket.objects.create(
                title=key, description="D", created_by=self.player, category_id=key
            )

        self.assertEqual(before, self.listing_queries())


class TestConcurrentDuplicates(CategoryTestCase):
    def test_a_duplicate_that_slips_past_the_check_is_a_400(self) -> None:
        with mock.patch("server.ticket.api._name_error", return_value=None):
            created = self.call("post", "/categories", self.staff, {"name": "Tech"})
            renamed = self.call("put", "/categories/Other", self.staff, {"name": "Tech"})

        self.assertEqual((400, 400), (created.status_code, renamed.status_code))

    def test_the_order_stops_at_the_largest_one(self) -> None:
        TicketCategory.objects.filter(key="Other").update(order=32767)

        response = self.call("post", "/categories", self.staff, {"name": "Last"})

        self.assertEqual(32767, response.json()["order"])


class TestOddStoredValues(TransactionTestCase):
    def migrate(self, target: str) -> Any:
        executor = MigrationExecutor(connection)
        executor.migrate([("server", target)])
        return executor.loader.project_state([("server", target)]).apps

    def tearDown(self) -> None:
        self.migrate("0176_ticket_categories")

    def test_blank_miscased_and_unknown_values_become_valid_keys(self) -> None:
        before = self.migrate("0175_seed_committees")
        user = before.get_model("server", "User").objects.create(username="u")
        # Its own: a transactional test before this one may have emptied the seeds.
        committee = before.get_model("server", "Committee").objects.create(
            name="Odd values", slug="odd-values"
        )
        for value in ("", "other", "Legacy", " Tech"):
            before.get_model("server", "Ticket").objects.create(
                title=value, description="D", created_by=user, category=value
            )
        for value in ("", "other", "Legacy", " Tech"):
            before.get_model("server", "TicketRoute").objects.create(
                category=value, committee=committee
            )

        after = self.migrate("0176_ticket_categories")

        tickets = after.get_model("server", "Ticket").objects.order_by("id")
        self.assertEqual([None, "Other", "Legacy", "Tech"], [t.category_id for t in tickets])
        routes = after.get_model("server", "TicketRoute").objects.filter(committee_id=committee.id)
        self.assertEqual(
            ["Other", "Legacy", "Tech"], [r.category_id for r in routes.order_by("id")]
        )
        legacy = after.get_model("server", "TicketCategory").objects.get(key="Legacy")
        self.assertTrue(legacy.is_retired)
