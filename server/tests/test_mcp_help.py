import datetime
import inspect
import sys
from typing import Any

from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

from server.committee.models import Committee, Role, TicketRoute
from server.core.models import User
from server.mcp.registry import TOOLS
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_invitations import McpToolCase
from server.ticket.models import Ticket, TicketCategory, TicketMessage


class HelpCase(McpToolCase):
    def setUp(self) -> None:
        super().setUp()
        self.other = User.objects.create(
            username="o@x.com", email="o@x.com", first_name="Om", last_name="Das"
        )
        make_token(self.other, "otok", scope="hub:read hub:write")
        self.category = TicketCategory.objects.create(key="payments", name="Payments")
        self.committee = Committee.objects.create(name="Ops", slug="ops")
        TicketRoute.objects.create(category=self.category, committee=self.committee)

    def handler(self) -> str:
        user = User.objects.create(
            username="h@x.com", email="h@x.com", first_name="Hema", last_name="Iyer"
        )
        Role.objects.create(
            committee=self.committee,
            user=user,
            title="Member",
            start_date=datetime.date(2020, 1, 1),
        )
        make_token(user, "htok", scope="hub:read hub:write")
        self.handling = user
        return "htok"

    def ticket(self, title: str = "Refund help", **kw: object) -> Ticket:
        kw.setdefault("created_by", self.other)
        return Ticket.objects.create(title=title, description="Need money back", **kw)


class TestListTickets(HelpCase):
    def test_lists_public_tickets_with_paging(self) -> None:
        self.ticket("One")
        self.ticket("Two", category=self.category, priority="HIG")

        data = self.data("list_tickets", {})

        self.assertEqual(["Two", "One"], [t["title"] for t in data["tickets"]])
        top = data["tickets"][0]
        self.assertEqual("Payments", top["category_name"])
        self.assertEqual("payments", top["category"])
        self.assertEqual("HIG", top["priority"])
        self.assertEqual("Om Das", top["created_by"])
        self.assertEqual(2, data["total"])
        self.assertEqual(1, data["page"])
        self.assertFalse(data["has_more"])
        self.assertNotIn("o@x.com", str(data))

    def test_filters(self) -> None:
        self.ticket("Open one")
        self.ticket("Done one", status="RES")
        self.ticket("Mine", created_by=self.user)

        def titles(**args: Any) -> set[str]:
            return {t["title"] for t in self.data("list_tickets", args)["tickets"]}

        self.assertEqual({"Open one", "Mine"}, titles(status=["OPN"]))
        self.assertEqual({"Done one"}, titles(status=["RES"]))
        self.assertEqual({"Mine"}, titles(mine=True))
        self.ticket("Assigned").assignees.add(self.user)
        self.assertEqual({"Assigned"}, titles(assigned=True))
        self.assertEqual({"Open one"}, titles(q="open"))

    def test_someone_elses_private_ticket_is_invisible(self) -> None:
        private = self.ticket("Secret", is_private=True)

        self.assertEqual([], self.data("list_tickets", {})["tickets"])
        self.assertTrue(
            self.failure("get_ticket", {"ticket_id": private.id}).startswith("Ticket not found")
        )
        self.assertEqual(1, len(self.data("list_tickets", {}, bearer="otok")["tickets"]))

    def test_waiting_on_us_is_for_handlers_only(self) -> None:
        message = self.failure("list_tickets", {"waiting_on_us": True})

        self.assertIn("staff and committee members", message)

    def test_waiting_on_us_keeps_open_tickets_whose_last_word_is_not_a_handlers(self) -> None:
        bearer = self.handler()
        unanswered = self.ticket("Unanswered", category=self.category)
        asked_again = self.ticket("Asked again", category=self.category)
        answered = self.ticket("Answered", category=self.category)
        self.ticket("Resolved", category=self.category, status="RES")
        self.ticket("Not ours")
        for ticket, sender in [
            (asked_again, self.handling),
            (asked_again, self.other),
            (answered, self.other),
            (answered, self.handling),
        ]:
            TicketMessage.objects.create(ticket=ticket, sender=sender, message="hi")

        data = self.data("list_tickets", {"waiting_on_us": True}, bearer=bearer)

        self.assertEqual({unanswered.id, asked_again.id}, {t["ticket_id"] for t in data["tickets"]})


class TestWaitingQueries(HelpCase):
    def test_the_number_of_queries_does_not_grow_with_the_tickets(self) -> None:
        bearer = self.handler()

        def count(tickets: int) -> int:
            for n in range(tickets):
                ticket = self.ticket(f"T{tickets}-{n}", category=self.category)
                sender = self.handling if n % 2 else self.other
                TicketMessage.objects.create(ticket=ticket, sender=sender, message="hi")
            with CaptureQueriesContext(connection) as queries:
                self.data("list_tickets", {"waiting_on_us": True}, bearer=bearer)
            return len(queries)

        self.assertEqual(count(2), count(20))


class TestGetTicket(HelpCase):
    def test_the_thread(self) -> None:
        ticket = self.ticket(category=self.category)
        TicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            message="Any news?",
            attachment="https://files.example.com/secret.pdf",
        )
        gone = TicketMessage.objects.create(ticket=ticket, sender=self.user, message="oops")
        gone.is_deleted = True
        gone.save()

        data = self.data("get_ticket", {"ticket_id": ticket.id})

        self.assertEqual(ticket.id, data["ticket_id"])
        self.assertEqual("Need money back", data["description"])
        self.assertEqual(1, len(data["messages"]))
        message = data["messages"][0]
        self.assertEqual("Any news?", message["text"])
        self.assertEqual("Asha Rao", message["from"])
        self.assertTrue(message["has_attachment"])
        self.assertEqual({"message_id", "from", "at", "text", "has_attachment"}, set(message))
        self.assertNotIn("secret.pdf", str(data))
        self.assertNotIn("o@x.com", str(data))
        self.assertFalse(data["can_handle"])

    def test_a_long_thread_keeps_the_first_and_the_newest_messages(self) -> None:
        ticket = self.ticket()
        for n in range(8):
            TicketMessage.objects.create(
                ticket=ticket, sender=self.other, message=f"m{n} " + "x" * 9000
            )

        data = self.data("get_ticket", {"ticket_id": ticket.id})

        starts = [m["text"].split()[0] for m in data["messages"]]
        self.assertLess(len(starts), 8)
        self.assertEqual("m0", starts[0])
        self.assertEqual("m7", starts[-1])
        self.assertEqual(sorted(starts), starts)
        self.assertEqual(8, data["truncated"]["total"])
        self.assertIn("first message", data["truncated"]["hint"])

    def test_a_missing_ticket(self) -> None:
        self.assertTrue(self.failure("get_ticket", {"ticket_id": 99999}))


class TestAgentsOnlyRead(HelpCase):
    def test_raising_replying_triaging_and_upvoting_are_left_to_hub(self) -> None:
        gone = {"create_ticket", "reply_to_ticket", "update_ticket", "upvote_ticket"}
        self.assertEqual(set(), gone & TOOLS.keys())
        self.assertFalse(TOOLS["list_tickets"].writes or TOOLS["get_ticket"].writes)
        for tool in TOOLS.values():
            if tool.writes:
                module = sys.modules[tool.handler.__module__]
                self.assertNotIn("/api/ticket", inspect.getsource(module), tool.name)
        kinds = TOOLS["create_upload_link"].input_schema["properties"]["kind"]["enum"]
        self.assertNotIn("ticket_attachment", kinds)

    def test_each_ticket_links_to_its_hub_page(self) -> None:
        ticket = self.ticket(category=self.category)
        url = f"{settings.PUBLIC_URL}/tickets/{ticket.pk}"

        self.assertEqual(url, self.data("list_tickets", {})["tickets"][0]["url"])
        self.assertEqual(url, self.data("get_ticket", {"ticket_id": ticket.pk})["url"])
        waiting = self.data("list_tickets", {"waiting_on_us": True}, bearer=self.handler())
        self.assertEqual([url], [t["url"] for t in waiting["tickets"]])
