import json
from typing import Any

from django.core import mail
from django.test import Client, TestCase

from server.core.models import User
from server.ticket.models import Ticket, TicketMessage


def make_user(username: str, is_staff: bool = False) -> User:
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", is_staff=is_staff
    )


class TicketTestCase(TestCase):
    def setUp(self) -> None:
        self.creator = make_user("creator")
        self.outsider = make_user("outsider")
        self.staff = make_user("staff", is_staff=True)
        self.ticket = Ticket.objects.create(
            title="My address", description="Sensitive", created_by=self.creator
        )

    def as_user(self, user: User) -> Client:
        client = Client()
        client.force_login(user)
        return client

    def put(self, user: User, data: dict[str, Any]) -> Any:
        return self.as_user(user).put(
            f"/api/ticket/{self.ticket.id}", data=json.dumps(data), content_type="application/json"
        )

    def listed_ids(self, user: User, query: str = "") -> list[int]:
        response = self.as_user(user).get(f"/api/ticket/{query}")
        self.assertEqual(200, response.status_code)
        return [ticket["id"] for ticket in response.json()]


class TestPrivateTickets(TicketTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ticket.is_private = True
        self.ticket.save()

    def test_create_private_ticket(self) -> None:
        response = self.as_user(self.outsider).post(
            "/api/ticket/",
            data=json.dumps({"title": "Mine", "description": "Private", "is_private": True}),
            content_type="application/json",
        )
        self.assertEqual(201, response.status_code)
        self.assertTrue(response.json()["is_private"])
        self.assertTrue(Ticket.objects.get(id=response.json()["id"]).is_private)

    def test_tickets_are_public_by_default(self) -> None:
        response = self.as_user(self.outsider).post(
            "/api/ticket/",
            data=json.dumps({"title": "Mine", "description": "Public"}),
            content_type="application/json",
        )
        self.assertFalse(response.json()["is_private"])

    def test_list_hides_private_ticket_from_others(self) -> None:
        self.assertNotIn(self.ticket.id, self.listed_ids(self.outsider))

    def test_list_shows_private_ticket_to_creator_and_staff(self) -> None:
        self.assertIn(self.ticket.id, self.listed_ids(self.creator))
        self.assertIn(self.ticket.id, self.listed_ids(self.staff))

    def test_detail_is_not_found_for_others(self) -> None:
        response = self.as_user(self.outsider).get(f"/api/ticket/{self.ticket.id}")
        self.assertEqual(404, response.status_code)

    def test_detail_is_visible_to_creator_and_staff(self) -> None:
        for user in (self.creator, self.staff):
            response = self.as_user(user).get(f"/api/ticket/{self.ticket.id}")
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.json()["is_private"])

    def test_others_cannot_reply(self) -> None:
        response = self.as_user(self.outsider).post(
            f"/api/ticket/{self.ticket.id}/message",
            data={"message_details": json.dumps({"message": "Snooping"})},
        )
        self.assertEqual(404, response.status_code)
        self.assertFalse(TicketMessage.objects.filter(ticket=self.ticket).exists())

    def test_others_cannot_update(self) -> None:
        response = self.put(self.outsider, {"is_private": False})
        self.assertEqual(404, response.status_code)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_private)

    def test_creator_can_make_it_public_again(self) -> None:
        response = self.put(self.creator, {"is_private": False})
        self.assertEqual(200, response.status_code)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.is_private)

    def test_staff_can_change_privacy(self) -> None:
        self.assertEqual(200, self.put(self.staff, {"is_private": False}).status_code)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.is_private)
        self.assertEqual(200, self.put(self.staff, {"is_private": True}).status_code)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_private)

    def test_leaving_privacy_out_of_an_update_keeps_it(self) -> None:
        self.assertEqual(200, self.put(self.creator, {"status": "RES"}).status_code)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_private)

    def test_reply_is_not_emailed_to_someone_who_replied_while_it_was_public(self) -> None:
        # The outsider replied back when the ticket was public; staff too.
        TicketMessage.objects.create(ticket=self.ticket, sender=self.outsider, message="Me too")
        TicketMessage.objects.create(ticket=self.ticket, sender=self.staff, message="On it")

        response = self.as_user(self.creator).post(
            f"/api/ticket/{self.ticket.id}/message",
            data={"message_details": json.dumps({"message": "My new address is ..."})},
        )

        self.assertEqual(201, response.status_code)
        recipients = {address for email in mail.outbox for address in email.to}
        self.assertIn(self.staff.email, recipients)
        self.assertNotIn(self.outsider.email, recipients)

    def test_reply_is_not_emailed_to_an_assignee_who_cannot_open_it(self) -> None:
        # The API lets staff assign anyone, but only staff can open a private ticket.
        self.ticket.assigned_to = self.outsider
        self.ticket.save()

        self.as_user(self.creator).post(
            f"/api/ticket/{self.ticket.id}/message",
            data={"message_details": json.dumps({"message": "My new address is ..."})},
        )

        recipients = {address for email in mail.outbox for address in email.to}
        self.assertNotIn(self.outsider.email, recipients)


class TestUpvotes(TicketTestCase):
    def upvote(self, user: User, method: str = "post") -> Any:
        client = self.as_user(user)
        return getattr(client, method)(f"/api/ticket/{self.ticket.id}/upvote")

    def test_upvoting_counts_once_per_person(self) -> None:
        self.assertEqual(200, self.upvote(self.outsider).status_code)
        response = self.upvote(self.outsider)  # a double click

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()["upvote_count"])
        self.assertTrue(response.json()["has_upvoted"])
        self.assertEqual(200, self.upvote(self.staff).status_code)
        self.assertEqual(2, self.ticket.upvoters.count())

    def test_taking_an_upvote_back(self) -> None:
        self.upvote(self.outsider)
        response = self.upvote(self.outsider, "delete")

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["upvote_count"])
        self.assertFalse(response.json()["has_upvoted"])
        self.assertEqual(200, self.upvote(self.outsider, "delete").status_code)

    def test_cannot_upvote_own_ticket(self) -> None:
        self.assertEqual(400, self.upvote(self.creator).status_code)
        self.assertEqual(0, self.ticket.upvoters.count())

    def test_private_ticket_cannot_be_upvoted(self) -> None:
        self.ticket.is_private = True
        self.ticket.save()

        self.assertEqual(404, self.upvote(self.outsider).status_code)
        self.assertEqual(400, self.upvote(self.staff).status_code)
        self.assertEqual(0, self.ticket.upvoters.count())

    def test_detail_says_whether_you_upvoted(self) -> None:
        self.upvote(self.outsider)

        mine = self.as_user(self.outsider).get(f"/api/ticket/{self.ticket.id}").json()
        theirs = self.as_user(self.staff).get(f"/api/ticket/{self.ticket.id}").json()

        self.assertEqual((1, True), (mine["upvote_count"], mine["has_upvoted"]))
        self.assertEqual((1, False), (theirs["upvote_count"], theirs["has_upvoted"]))

    def test_list_counts_upvotes_and_messages_separately(self) -> None:
        # Two counts over two joins multiply each other unless kept distinct.
        for user in (self.outsider, self.staff, make_user("third")):
            self.ticket.upvoters.add(user)
        for text in ("One", "Two"):
            TicketMessage.objects.create(ticket=self.ticket, sender=self.creator, message=text)

        [listed] = self.as_user(self.outsider).get("/api/ticket/").json()

        self.assertEqual(3, listed["upvote_count"])
        self.assertEqual(2, listed["message_count"])
        self.assertTrue(listed["has_upvoted"])

    def test_list_sorted_by_upvotes(self) -> None:
        popular = Ticket.objects.create(title="Popular", description="-", created_by=self.creator)
        popular.upvoters.add(self.outsider, self.staff)
        self.ticket.upvoters.add(self.outsider)
        newest = Ticket.objects.create(title="Newest", description="-", created_by=self.creator)

        ids = self.listed_ids(self.outsider, "?sort=upvotes")

        self.assertEqual([popular.id, self.ticket.id, newest.id], ids)
        self.assertEqual(newest.id, self.listed_ids(self.outsider)[0])

    def test_unknown_sort_is_rejected(self) -> None:
        response = self.as_user(self.outsider).get("/api/ticket/?sort=upvote")
        self.assertEqual(422, response.status_code)
