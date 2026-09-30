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
