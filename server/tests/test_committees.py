import datetime
import json
from importlib import import_module
from typing import Any

from django.apps import apps
from django.core import mail
from django.test import Client, TestCase

from server.committee.models import Committee, Role, TicketRoute
from server.committee.routing import chairs_for
from server.core.models import User
from server.ticket.access import can_handle
from server.ticket.models import Ticket
from server.utils import today

DAY = datetime.timedelta(days=1)


def make_user(username: str, is_staff: bool = False) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        first_name=username.title(),
        is_staff=is_staff,
    )


class CommitteeTestCase(TestCase):
    """The migrations seed the committees: Competitions handles Competitions
    and Tournament tickets, Operations handles Other, and Finance has no route."""

    def setUp(self) -> None:
        self.competitions = Committee.objects.get(slug="competitions")
        self.operations = Committee.objects.get(slug="operations")
        self.finance = Committee.objects.get(slug="finance")
        self.staff = make_user("staff", is_staff=True)
        self.creator = make_user("creator")
        self.chair = make_user("chair")
        self.member = make_user("member")
        self.outsider = make_user("outsider")
        self.give_role(self.chair, self.competitions, is_chair=True)
        self.give_role(self.member, self.competitions)

    def give_role(
        self,
        user: User,
        committee: Committee,
        is_chair: bool = False,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> Role:
        return Role.objects.create(
            committee=committee,
            user=user,
            title="Chair" if is_chair else "Member",
            is_chair=is_chair,
            start_date=start or today() - 30 * DAY,
            end_date=end,
        )

    def make_ticket(self, category: str = "Competitions", is_private: bool = True) -> Ticket:
        return Ticket.objects.create(
            title="Fixtures",
            description="Wrong",
            created_by=self.creator,
            category_id=category,
            is_private=is_private,
        )

    def call(self, method: str, path: str, user: User | None = None, data: Any = None) -> Any:
        client = Client()
        if user:
            client.force_login(user)
        if method in ("post", "put"):
            return getattr(client, method)(
                f"/api{path}", data=json.dumps(data), content_type="application/json"
            )
        return getattr(client, method)(f"/api{path}")

    def post_ticket(self, user: User, category: str, is_private: bool = False) -> Any:
        return self.call(
            "post",
            "/ticket/",
            user,
            {
                "title": "Help",
                "description": "Please",
                "category": category,
                "is_private": is_private,
            },
        )

    def recipients(self) -> set[str]:
        return {address for email in mail.outbox for address in email.to}


class TestRouting(CommitteeTestCase):
    def test_a_new_ticket_is_assigned_to_every_chair_and_they_are_emailed(self) -> None:
        self.give_role(self.outsider, self.competitions, is_chair=True)

        response = self.post_ticket(self.creator, "Competitions")

        self.assertEqual(201, response.status_code)
        ticket = Ticket.objects.get(id=response.json()["id"])
        self.assertEqual({self.chair, self.outsider}, set(ticket.assignees.all()))
        self.assertEqual({self.chair.email, self.outsider.email}, self.recipients())
        self.assertTrue(all("assigned to you" in email.subject for email in mail.outbox))

    def test_a_category_routes_to_every_committee_it_lists(self) -> None:
        finance_chair = make_user("finance_chair")
        self.give_role(finance_chair, self.finance, is_chair=True)
        TicketRoute.objects.create(category_id="Competitions", committee=self.finance)

        self.assertEqual({self.chair, finance_chair}, set(chairs_for("Competitions")))

    def test_a_person_chairing_two_routed_committees_is_assigned_once(self) -> None:
        self.give_role(self.chair, self.finance, is_chair=True)
        TicketRoute.objects.create(category_id="Competitions", committee=self.finance)

        self.assertEqual([self.chair], list(chairs_for("Competitions")))

    def test_a_category_with_no_route_stays_unassigned(self) -> None:
        TicketRoute.objects.filter(category__key="Other").delete()

        response = self.post_ticket(self.creator, "Other")

        self.assertEqual([], response.json()["assignees"])
        self.assertEqual(set(), self.recipients())

    def test_a_chair_whose_term_has_ended_or_not_started_is_not_assigned(self) -> None:
        self.give_role(self.outsider, self.competitions, is_chair=True, end=today())
        future = make_user("future")
        self.give_role(future, self.competitions, is_chair=True, start=today() + DAY)

        self.assertEqual([self.chair], list(chairs_for("Competitions")))

    def test_a_ticket_with_no_category_goes_to_no_chair(self) -> None:
        self.give_role(self.outsider, self.finance, is_chair=True)

        self.assertEqual([], list(chairs_for(None)))
        response = self.post_ticket(self.creator, "")

        self.assertEqual([], response.json()["assignees"])
        self.assertEqual(set(), self.recipients())

    def test_a_member_who_is_not_chair_is_not_assigned(self) -> None:
        self.assertNotIn(self.member, chairs_for("Competitions"))


class TestAccess(CommitteeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ticket = self.make_ticket()

    def put(self, user: User, data: dict[str, Any]) -> Any:
        return self.call("put", f"/ticket/{self.ticket.id}", user, data)

    def test_a_member_sees_the_private_tickets_of_their_committee(self) -> None:
        response = self.call("get", f"/ticket/{self.ticket.id}", self.member)

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["can_handle"])

    def test_a_member_of_another_committee_cannot(self) -> None:
        self.give_role(self.outsider, self.operations)

        self.assertEqual(
            404, self.call("get", f"/ticket/{self.ticket.id}", self.outsider).status_code
        )

    def test_a_member_can_set_status_and_priority_but_not_the_title_or_category(self) -> None:
        response = self.put(
            self.member, {"status": "RES", "priority": "URG", "title": "New", "category": "Tech"}
        )

        self.assertEqual(200, response.status_code)
        self.ticket.refresh_from_db()
        self.assertEqual(("RES", "URG"), (self.ticket.status, self.ticket.priority))
        self.assertEqual(("Fixtures", "Competitions"), (self.ticket.title, self.ticket.category_id))

    def test_staff_change_the_title_and_category(self) -> None:
        self.put(self.staff, {"title": "New", "category": "Tech"})

        self.ticket.refresh_from_db()
        self.assertEqual(("New", "Tech"), (self.ticket.title, self.ticket.category_id))

    def test_a_former_member_cannot(self) -> None:
        Role.objects.filter(user=self.member).update(end_date=today())

        self.assertEqual(
            404, self.call("get", f"/ticket/{self.ticket.id}", self.member).status_code
        )

    def test_a_member_can_reply(self) -> None:
        response = self.client_for(self.member).post(
            f"/api/ticket/{self.ticket.id}/message",
            data={"message_details": json.dumps({"message": "On it"})},
        )

        self.assertEqual(201, response.status_code)

    def test_a_member_of_an_unrouted_committee_cannot_handle_an_uncategorised_ticket(self) -> None:
        self.give_role(self.outsider, self.finance)
        ticket = self.make_ticket("")
        Ticket.objects.filter(id=ticket.id).update(category_id=None)

        response = self.call("get", f"/ticket/{ticket.id}", self.outsider)

        self.assertEqual(404, response.status_code)
        self.assertFalse(can_handle(self.outsider, Ticket.objects.get(id=ticket.id)))

    def test_the_detail_lists_the_routed_committees(self) -> None:
        response = self.call("get", f"/ticket/{self.ticket.id}", self.member)

        self.assertEqual(["competitions"], response.json()["routed_committees"])

    def test_a_public_ticket_of_another_category_is_visible_but_not_handled(self) -> None:
        public = self.make_ticket("Tech", is_private=False)

        response = self.call("get", f"/ticket/{public.id}", self.member)

        self.assertFalse(response.json()["can_handle"])
        self.assertEqual(
            403,
            self.call("put", f"/ticket/{public.id}", self.member, {"status": "RES"}).status_code,
        )

    def test_ending_a_term_removes_access_the_same_day(self) -> None:
        role = Role.objects.get(user=self.member)

        self.call(
            "put", f"/committees/roles/{role.id}", self.staff, {"end_date": today().isoformat()}
        )

        self.assertEqual(
            404, self.call("get", f"/ticket/{self.ticket.id}", self.member).status_code
        )

    def client_for(self, user: User) -> Client:
        client = Client()
        client.force_login(user)
        return client


class TestAssignees(CommitteeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ticket = self.make_ticket(is_private=False)

    def path(self, user: User) -> str:
        return f"/ticket/{self.ticket.id}/assignees/{user.id}"

    def test_handlers_add_and_remove_assignees(self) -> None:
        self.call("post", self.path(self.member), self.chair)
        self.assertEqual([self.member], list(self.ticket.assignees.all()))

        response = self.call("delete", self.path(self.member), self.chair)

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["assignees"])

    def test_someone_without_a_role_cannot_be_assigned(self) -> None:
        response = self.call("post", self.path(self.outsider), self.staff)

        self.assertEqual(400, response.status_code)
        self.assertFalse(self.ticket.assignees.exists())

    def test_staff_can_be_assigned(self) -> None:
        self.call("post", self.path(self.staff), self.chair)

        self.assertEqual([self.staff], list(self.ticket.assignees.all()))

    def test_a_non_handler_gets_403(self) -> None:
        self.assertEqual(403, self.call("post", self.path(self.member), self.creator).status_code)
        self.assertEqual(403, self.call("delete", self.path(self.member), self.creator).status_code)

    def test_adding_someone_emails_them_but_adding_yourself_does_not(self) -> None:
        self.call("post", self.path(self.member), self.chair)
        self.assertEqual({self.member.email}, self.recipients())

        mail.outbox.clear()
        self.call("post", self.path(self.chair), self.chair)
        self.assertEqual(set(), self.recipients())

    def test_adding_someone_already_assigned_does_not_email_again(self) -> None:
        self.ticket.assignees.add(self.member)

        self.call("post", self.path(self.member), self.chair)

        self.assertEqual(set(), self.recipients())


class TestMessageEmails(CommitteeTestCase):
    def reply(self, ticket: Ticket, user: User) -> None:
        client = Client()
        client.force_login(user)
        client.post(
            f"/api/ticket/{ticket.id}/message",
            data={"message_details": json.dumps({"message": "Update"})},
        )

    def test_a_private_ticket_reaches_current_members_and_not_former_ones(self) -> None:
        former = make_user("former")
        self.give_role(former, self.competitions, end=today())
        ticket = self.make_ticket()
        ticket.assignees.add(self.chair, former)

        self.reply(ticket, self.creator)

        self.assertEqual({self.chair.email}, self.recipients())

    def test_an_uncategorised_private_ticket_reaches_no_committee_member(self) -> None:
        self.give_role(self.outsider, self.finance)
        ticket = self.make_ticket()
        Ticket.objects.filter(id=ticket.id).update(category_id=None)
        ticket.refresh_from_db()
        ticket.assignees.add(self.outsider)

        self.reply(ticket, self.creator)

        self.assertEqual(set(), self.recipients())

    def test_every_assignee_of_a_public_ticket_is_emailed(self) -> None:
        ticket = self.make_ticket(is_private=False)
        ticket.assignees.add(self.chair, self.member)

        self.reply(ticket, self.creator)

        self.assertEqual({self.chair.email, self.member.email}, self.recipients())

    def test_the_sender_is_not_emailed(self) -> None:
        ticket = self.make_ticket()
        ticket.assignees.add(self.chair, self.member)

        self.reply(ticket, self.chair)

        self.assertEqual({self.member.email, self.creator.email}, self.recipients())


class TestPublicApi(CommitteeTestCase):
    def test_only_current_roles_are_listed_chairs_first(self) -> None:
        self.give_role(self.outsider, self.competitions, end=today())

        response = self.call("get", "/committees/")

        self.assertEqual(200, response.status_code)
        committees = response.json()
        self.assertEqual("executive-board", committees[0]["slug"])
        competitions = next(c for c in committees if c["slug"] == "competitions")
        self.assertEqual(
            [(self.chair.id, True), (self.member.id, False)],
            [(role["person"]["id"], role["is_chair"]) for role in competitions["roles"]],
        )

    def test_the_detail_has_past_roles_newest_first(self) -> None:
        old = self.give_role(self.outsider, self.competitions, end=today() - 20 * DAY)
        older = self.give_role(make_user("older"), self.competitions, end=today() - 25 * DAY)

        detail = self.call("get", "/committees/competitions").json()

        self.assertEqual([old.id, older.id], [role["id"] for role in detail["past_roles"]])
        self.assertEqual(2, len(detail["roles"]))

    def test_no_personal_details_are_exposed(self) -> None:
        self.member.phone = "9999999999"
        self.member.save()

        body = self.call("get", "/committees/competitions").content.decode()

        for secret in (self.member.email, "9999999999", "date_of_birth", "phone"):
            self.assertNotIn(secret, body)

    def test_an_unknown_slug_is_404(self) -> None:
        self.assertEqual(404, self.call("get", "/committees/nope").status_code)


class TestStaffApi(CommitteeTestCase):
    def test_non_staff_get_403(self) -> None:
        role = Role.objects.get(user=self.member)
        body = {
            "name": "New",
            "user_id": self.outsider.id,
            "title": "x",
            "start_date": "2026-01-01",
        }
        for method, path in [
            ("post", "/committees/"),
            ("put", "/committees/competitions"),
            ("post", "/committees/competitions/roles"),
            ("put", f"/committees/roles/{role.id}"),
            ("delete", f"/committees/roles/{role.id}"),
            ("get", "/ticket/routes"),
            ("put", "/ticket/routes/Other"),
        ]:
            with self.subTest(path=path, method=method):
                self.assertEqual(
                    403, self.call(method, path, self.chair, body | {"committees": []}).status_code
                )

    def test_staff_create_and_update_a_committee(self) -> None:
        created = self.call("post", "/committees/", self.staff, {"name": "Youth Camp", "order": 12})
        self.assertEqual(201, created.status_code)
        self.assertEqual("youth-camp", created.json()["slug"])

        updated = self.call(
            "put", "/committees/youth-camp", self.staff, {"name": "Youth", "email": "y@x.org"}
        )
        self.assertEqual(("Youth", "y@x.org"), (updated.json()["name"], updated.json()["email"]))

    def test_the_manage_slug_and_duplicate_names_are_refused(self) -> None:
        for name in ("Manage", "Tech"):
            self.assertEqual(
                400, self.call("post", "/committees/", self.staff, {"name": name}).status_code
            )

    def test_a_name_with_no_letters_is_refused(self) -> None:
        self.assertEqual(
            400, self.call("post", "/committees/", self.staff, {"name": "!!!"}).status_code
        )

    def test_order_must_fit_the_column(self) -> None:
        for order in (-1, 32768):
            response = self.call(
                "post", "/committees/", self.staff, {"name": "Big", "order": order}
            )
            self.assertEqual(422, response.status_code)

    def test_the_committee_carries_its_order(self) -> None:
        committees = self.call("get", "/committees/").json()

        self.assertEqual(1, next(c for c in committees if c["slug"] == "competitions")["order"])

    def test_a_future_term_overlapping_a_current_one_is_refused(self) -> None:
        body = {
            "user_id": self.member.id,
            "title": "Chair",
            "start_date": (today() + DAY).isoformat(),
        }

        response = self.call("post", "/committees/competitions/roles", self.staff, body)

        self.assertEqual(400, response.status_code)

    def test_a_term_after_an_ended_one_is_allowed_and_can_not_be_stretched_over_it(self) -> None:
        Role.objects.filter(user=self.member).update(end_date=today())
        later = self.give_role(self.member, self.competitions, start=today() + DAY)

        response = self.call(
            "put",
            f"/committees/roles/{later.id}",
            self.staff,
            {"start_date": (today() - DAY).isoformat()},
        )

        self.assertEqual(400, response.status_code)

    def test_a_duplicate_current_role_is_refused(self) -> None:
        body = {"user_id": self.member.id, "title": "Chair", "start_date": today().isoformat()}

        response = self.call("post", "/committees/competitions/roles", self.staff, body)

        self.assertEqual(400, response.status_code)
        self.assertEqual(1, Role.objects.filter(user=self.member).count())

    def test_someone_can_hold_roles_in_several_committees(self) -> None:
        body = {"user_id": self.member.id, "title": "Member", "start_date": today().isoformat()}

        response = self.call("post", "/committees/finance/roles", self.staff, body)

        self.assertEqual(201, response.status_code)

    def test_a_returning_member_can_be_added_after_their_term_ended(self) -> None:
        Role.objects.filter(user=self.member).update(end_date=today())
        body = {"user_id": self.member.id, "title": "Member", "start_date": today().isoformat()}

        self.assertEqual(
            201, self.call("post", "/committees/competitions/roles", self.staff, body).status_code
        )

    def test_a_term_cannot_end_before_it_starts(self) -> None:
        role = Role.objects.get(user=self.member)

        response = self.call(
            "put", f"/committees/roles/{role.id}", self.staff, {"end_date": "2000-01-01"}
        )

        self.assertEqual(400, response.status_code)

    def test_a_term_can_end_on_its_first_day(self) -> None:
        # Someone added today by mistake can still have their term ended today.
        role = Role.objects.get(user=self.member)
        Role.objects.filter(pk=role.pk).update(start_date=today())

        response = self.call(
            "put", f"/committees/roles/{role.id}", self.staff, {"end_date": today().isoformat()}
        )

        self.assertEqual(200, response.status_code)
        self.assertFalse(Role.objects.current().filter(pk=role.pk).exists())

    def test_only_the_end_date_can_be_cleared(self) -> None:
        role = Role.objects.get(user=self.member)

        for field in ("title", "is_chair", "start_date"):
            response = self.call("put", f"/committees/roles/{role.id}", self.staff, {field: None})
            self.assertEqual(400, response.status_code, field)
        reopened = self.call("put", f"/committees/roles/{role.id}", self.staff, {"end_date": None})
        self.assertEqual(200, reopened.status_code)

    def test_staff_delete_a_role(self) -> None:
        role = Role.objects.get(user=self.member)

        self.assertEqual(
            204, self.call("delete", f"/committees/roles/{role.id}", self.staff).status_code
        )
        self.assertFalse(Role.objects.filter(id=role.id).exists())

    def test_routing_replaces_a_categorys_rows(self) -> None:
        response = self.call(
            "put", "/ticket/routes/Payment", self.staff, {"committees": ["finance", "operations"]}
        )
        self.assertEqual(["operations", "finance"], response.json()["committees"])

        self.call("put", "/ticket/routes/Payment", self.staff, {"committees": ["finance"]})

        routes = self.call("get", "/ticket/routes", self.staff).json()
        self.assertEqual(7, len(routes))
        self.assertEqual(
            ["finance"], next(r for r in routes if r["category"] == "Payment")["committees"]
        )

    def test_routing_to_an_unknown_committee_is_refused(self) -> None:
        response = self.call("put", "/ticket/routes/Payment", self.staff, {"committees": ["nope"]})

        self.assertEqual(400, response.status_code)
        self.assertEqual(1, TicketRoute.objects.filter(category__key="Payment").count())


class TestMigrations(TestCase):
    def test_the_seed_creates_the_committees_and_routes(self) -> None:
        self.assertEqual(
            ["executive-board", "competitions", "operations", "tech", "finance", "governance"],
            list(Committee.objects.values_list("slug", flat=True)[:6]),
        )
        self.assertEqual(11, Committee.objects.count())
        routes = {
            (route.category_id, route.committee.name)
            for route in TicketRoute.objects.select_related("committee")
        }
        self.assertEqual(
            {
                ("Competitions", "Competitions"),
                ("Tournament", "Competitions"),
                ("Tech", "Tech"),
                ("Account", "Operations"),
                ("Payment", "Operations"),
                ("Subscription", "Operations"),
                ("Other", "Operations"),
            },
            routes,
        )
        self.assertTrue(Committee.objects.filter(slug="project-gamechangers").exists())

    def test_the_assignee_migration_copies_assigned_to(self) -> None:
        creator = make_user("creator")
        assignee = make_user("assignee")
        ticket = Ticket.objects.create(
            title="Old", description="x", created_by=creator, assigned_to=assignee
        )
        unassigned = Ticket.objects.create(title="New", description="x", created_by=creator)

        import_module("server.migrations.0174_ticket_assignees_from_assigned_to").copy_assigned_to(
            apps, None
        )

        self.assertEqual([assignee], list(ticket.assignees.all()))
        self.assertEqual([], list(unassigned.assignees.all()))
