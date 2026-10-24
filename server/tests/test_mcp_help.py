import datetime
from typing import Any
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from server.committee.models import Committee, Role, TicketRoute
from server.core.models import User
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


class TestCreateTicket(HelpCase):
    def create(self, args: dict[str, Any]) -> dict[str, Any]:
        result = self.confirmed("create_ticket", args)
        self.assertFalse(result["isError"], result)
        return dict(result["structuredContent"])

    def test_asks_first_and_shows_what_will_be_sent(self) -> None:
        args = {
            "title": "Cannot pay",
            "description": "Card fails " + "x" * 400,
            "category": "payments",
            "is_private": True,
        }

        asked = self.ask("create_ticket", args)

        text = asked["needs_confirmation"]
        for words in ("Cannot pay", "payments", "private", "Card fails", "emails"):
            self.assertIn(words, text)
        self.assertLess(len(text), 600)
        self.assertEqual(0, Ticket.objects.count())

    def test_creates_after_the_yes(self) -> None:
        data = self.create(
            {"title": "Cannot pay", "description": "Card fails", "category": "payments"}
        )

        ticket = Ticket.objects.get(pk=data["ticket_id"])
        self.assertEqual(self.user, ticket.created_by)
        self.assertEqual("MED", ticket.priority)
        self.assertFalse(ticket.is_private)
        self.assertEqual("payments", ticket.category_id)

    def test_private_and_priority(self) -> None:
        data = self.create(
            {"title": "ID", "description": "d", "priority": "URG", "is_private": True},
        )

        ticket = Ticket.objects.get(pk=data["ticket_id"])
        self.assertTrue(ticket.is_private)
        self.assertEqual("URG", ticket.priority)

    def test_a_long_title_is_refused(self) -> None:
        self.assertTrue(self.failure("create_ticket", {"title": "x" * 201, "description": "d"}))
        self.assertEqual(0, Ticket.objects.count())

    def test_an_unknown_priority_is_refused(self) -> None:
        self.assertTrue(
            self.failure("create_ticket", {"title": "t", "description": "d", "priority": "SOON"})
        )

    def test_an_unknown_category_lists_the_real_ones(self) -> None:
        result = self.confirmed(
            "create_ticket", {"title": "t", "description": "d", "category": "zzz"}
        )

        self.assertTrue(result["isError"])
        self.assertIn("payments", result["structuredContent"]["valid_categories"])
        self.assertEqual(0, Ticket.objects.count())

    def test_the_hourly_email_limit_applies(self) -> None:
        args = {"title": "t", "description": "d"}
        state = self.ask("create_ticket", args)["confirmation"]

        with mock.patch("server.mcp.registry.over_limit", return_value=True):
            result = self.call("create_ticket", {**args, "confirmation": state})

        self.assertIn("a lot of emails", result["structuredContent"]["message"])
        self.assertEqual(0, Ticket.objects.count())

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_only_a_confirmed_ticket_spends_the_budget(self) -> None:
        self.addCleanup(cache.clear)
        key = f"mcp-email:{self.user.pk}:{int(now().timestamp() // 3600)}"

        self.failure("create_ticket", {"title": "x" * 201, "description": "d"})
        self.ask("create_ticket", {"title": "t", "description": "d"})
        self.assertIsNone(cache.get(key))
        self.create({"title": "t", "description": "d"})

        self.assertEqual(1, cache.get(key))


class TestReplyToTicket(HelpCase):
    def test_asks_then_posts_and_emails(self) -> None:
        ticket = self.ticket()
        args = {"ticket_id": ticket.id, "message": "Thanks, still waiting"}

        asked = self.ask("reply_to_ticket", args)
        self.assertIn("Refund help", asked["needs_confirmation"])
        self.assertIn("Hub emails", asked["needs_confirmation"])
        self.assertEqual(0, ticket.messages.count())
        result = self.call("reply_to_ticket", {**args, "confirmation": asked["confirmation"]})

        self.assertFalse(result["isError"], result)
        self.assertEqual(["Thanks, still waiting"], [m.message for m in ticket.messages.all()])
        self.assertEqual(self.user, ticket.messages.get().sender)
        self.assertEqual(["o@x.com"], [to for m in mail.outbox for to in m.to])

    def test_the_callers_own_name_is_not_among_those_emailed(self) -> None:
        self.user.first_name = "Asha "
        self.user.save()
        ticket = self.ticket()
        TicketMessage.objects.create(ticket=ticket, sender=self.user, message="first")

        asked = self.ask("reply_to_ticket", {"ticket_id": ticket.id, "message": "again"})

        self.assertIn("(Om Das)", asked["needs_confirmation"])

    def test_a_private_ticket_of_someone_else_is_not_found(self) -> None:
        ticket = self.ticket(is_private=True)

        message = self.failure("reply_to_ticket", {"ticket_id": ticket.id, "message": "hi"})

        self.assertTrue(message.startswith("Ticket not found"), message)
        self.assertEqual(0, ticket.messages.count())

    def test_the_hourly_email_limit_applies(self) -> None:
        ticket = self.ticket()
        args = {"ticket_id": ticket.id, "message": "hi"}
        state = self.ask("reply_to_ticket", args)["confirmation"]

        with mock.patch("server.mcp.registry.over_limit", return_value=True):
            result = self.call("reply_to_ticket", {**args, "confirmation": state})

        self.assertTrue(result["isError"])
        self.assertEqual(0, ticket.messages.count())


class TestUpvoteTicket(HelpCase):
    def test_upvote_and_undo(self) -> None:
        ticket = self.ticket()

        up = self.data("upvote_ticket", {"ticket_id": ticket.id})
        self.assertEqual(1, up["upvote_count"])
        self.assertTrue(up["has_upvoted"])
        down = self.data("upvote_ticket", {"ticket_id": ticket.id, "undo": True})
        self.assertEqual(0, down["upvote_count"])
        self.assertFalse(down["has_upvoted"])

    def test_not_your_own_or_a_private_ticket(self) -> None:
        own = self.ticket(created_by=self.user)
        private = self.ticket(is_private=True)

        self.assertIn("own ticket", self.failure("upvote_ticket", {"ticket_id": own.id}))
        self.assertTrue(self.failure("upvote_ticket", {"ticket_id": private.id}))
