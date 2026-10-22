import datetime
from typing import Any
from unittest import mock

from server.committee.models import Committee, Role, TicketRoute
from server.core.models import User
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.ticket.models import Ticket, TicketCategory
from server.utils import today


class HandlersTestCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        TicketRoute.objects.filter(category__key="Tech").delete()
        self.committee = Committee.objects.create(name="Helpdesk", slug="helpdesk")
        TicketRoute.objects.create(
            category=TicketCategory.objects.get(key="Tech"), committee=self.committee
        )
        self.role(self.user, self.committee)
        self.other = User.objects.create(username="o@x.com", email="o@x.com", first_name="Om")
        self.ticket = Ticket.objects.create(
            title="Broken", description="D", created_by=self.other, category_id="Tech"
        )

    def role(self, user: User, committee: Committee, **kw: Any) -> Role:
        return Role.objects.create(
            user=user,
            committee=committee,
            title="Member",
            start_date=today() - datetime.timedelta(days=1),
            **kw,
        )

    def ask(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        asked = self.call(name, arguments)["structuredContent"]
        self.assertFalse(asked["done"])
        return dict(asked)

    def confirmed(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        first = self.call(name, arguments)["structuredContent"]
        self.assertFalse(first["done"])
        return self.call(name, {**arguments, "confirmation": first["confirmation"]})


class TestUpdateTicket(HandlersTestCase):
    def test_hidden_from_players(self) -> None:
        self.assertIn("update_ticket", self.names(self.modern("tools/list")))
        Role.objects.update(end_date=today() - datetime.timedelta(days=1))

        self.assertNotIn("update_ticket", self.names(self.modern("tools/list")))

    def test_a_committee_member_sets_status_and_priority_after_saying_yes(self) -> None:
        args = {"ticket_id": self.ticket.pk, "status": "PRG", "priority": "HIG"}

        asked = self.ask("update_ticket", args)
        self.ticket.refresh_from_db()
        self.assertEqual("OPN", self.ticket.status)
        self.assertIn("status PRG", asked["needs_confirmation"])
        result = self.confirmed("update_ticket", args)

        self.assertFalse(result["isError"], result)
        self.ticket.refresh_from_db()
        self.assertEqual(("PRG", "HIG"), (self.ticket.status, self.ticket.priority))
        self.assertEqual(self.ticket.pk, result["structuredContent"]["ticket_id"])

    def test_a_bad_status_is_refused(self) -> None:
        result = self.call("update_ticket", {"ticket_id": self.ticket.pk, "status": "DONE"})

        self.assertTrue(result["isError"])
        self.ticket.refresh_from_db()
        self.assertEqual("OPN", self.ticket.status)

    def test_a_ticket_routed_elsewhere_is_not_theirs(self) -> None:
        Ticket.objects.filter(pk=self.ticket.pk).update(category_id="Payment")

        result = self.call("update_ticket", {"ticket_id": self.ticket.pk, "status": "RES"})

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])
        self.ticket.refresh_from_db()
        self.assertEqual("OPN", self.ticket.status)

    def test_only_staff_move_a_category(self) -> None:
        result = self.call("update_ticket", {"ticket_id": self.ticket.pk, "category": "Other"})

        self.assertTrue(result["isError"])
        self.ticket.refresh_from_db()
        self.assertEqual("Tech", self.ticket.category_id)

    def test_adding_an_assignee_asks_first_and_emails_once_confirmed(self) -> None:
        mate = User.objects.create(username="m@x.com", email="m@x.com", first_name="Mia")
        self.role(mate, self.committee)
        args = {"ticket_id": self.ticket.pk, "add_assignee_user_ids": [mate.pk]}

        with mock.patch("server.ticket.api.send_mail") as send:
            first = self.call("update_ticket", args)["structuredContent"]
            self.assertFalse(first["done"])
            self.assertIn("Mia", first["needs_confirmation"])
            self.assertEqual(0, self.ticket.assignees.count())
            result = self.call("update_ticket", {**args, "confirmation": first["confirmation"]})

        self.assertFalse(result["isError"], result)
        self.assertEqual([mate], list(self.ticket.assignees.all()))
        self.assertEqual(1, send.call_count)

    def test_removing_an_assignee_asks_first(self) -> None:
        self.ticket.assignees.add(self.user)
        args = {"ticket_id": self.ticket.pk, "remove_assignee_user_ids": [self.user.pk]}

        self.ask("update_ticket", args)
        self.assertEqual(1, self.ticket.assignees.count())
        result = self.confirmed("update_ticket", args)

        self.assertFalse(result["isError"], result)
        self.assertEqual(0, self.ticket.assignees.count())

    def test_someone_who_cannot_be_assigned_is_refused(self) -> None:
        result = self.confirmed(
            "update_ticket", {"ticket_id": self.ticket.pk, "add_assignee_user_ids": [self.other.pk]}
        )

        self.assertTrue(result["isError"])
        self.assertEqual(0, self.ticket.assignees.count())
