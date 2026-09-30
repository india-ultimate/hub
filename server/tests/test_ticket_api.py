import json
from importlib import import_module
from typing import Any

from django.apps import apps
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase

from server.core.models import User
from server.ticket.models import Ticket, TicketMessage
from server.ticket.search import search_words


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
        return [ticket["id"] for ticket in response.json()["items"]]


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

        [listed] = self.as_user(self.outsider).get("/api/ticket/").json()["items"]

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


class TestSearchWords(SimpleTestCase):
    def test_drops_short_filler_and_repeated_words(self) -> None:
        self.assertEqual(
            ["renew", "subscription"],
            search_words("Can't I renew the subscription, subscription?"),
        )

    def test_keeps_at_most_eight_words(self) -> None:
        words = search_words("one1 two2 three3 four4 five5 six6 seven7 eight8 nine9")
        self.assertEqual(
            ["one1", "two2", "three3", "four4", "five5", "six6", "seven7", "eight8"], words
        )

    def test_wildcards_are_split_away(self) -> None:
        self.assertEqual(["100"], search_words("100% a_b"))

    def test_only_filler_punctuation_or_emoji_is_no_search(self) -> None:
        for q in ("how can you", "   ", "?!", "\U0001f642\U0001f642"):
            self.assertEqual([], search_words(q), q)


class TestListing(TicketTestCase):
    def page(self, user: User, query: str = "") -> dict[str, Any]:
        response = self.as_user(user).get(f"/api/ticket/?{query}")
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def titles(self, user: User, query: str = "") -> list[str]:
        return [ticket["title"] for ticket in self.page(user, query)["items"]]

    def make(self, title: str, description: str = "-", **fields: Any) -> Ticket:
        fields.setdefault("created_by", self.creator)
        return Ticket.objects.create(title=title, description=description, **fields)

    def test_pages_hold_twenty_and_count_them_all(self) -> None:
        for n in range(25):
            self.make(f"Ticket {n}")

        first = self.page(self.outsider)
        second = self.page(self.outsider, "page=2")

        self.assertEqual((20, 26), (len(first["items"]), first["count"]))
        self.assertEqual((6, 26), (len(second["items"]), second["count"]))

    def test_a_page_past_the_end_is_empty_not_an_error(self) -> None:
        page = self.page(self.outsider, "page=99")
        self.assertEqual(([], 1), (page["items"], page["count"]))

    def test_newest_first_by_default(self) -> None:
        self.make("Newer")
        self.assertEqual(["Newer", "My address"], self.titles(self.outsider))

    def test_title_hits_rank_above_description_hits(self) -> None:
        self.make("Payment failed")
        self.make("Help", "my payment failed twice")  # newer, but a weaker match

        self.assertEqual(["Payment failed", "Help"], self.titles(self.outsider, "q=payment"))

    def test_score_says_whether_it_was_a_search(self) -> None:
        # The create page only suggests tickets that actually matched
        self.make("Payment failed")
        self.assertEqual(2, self.page(self.outsider, "q=payment")["items"][0]["score"])
        for query in ("q=How+do+I+get", ""):
            scores = {t["score"] for t in self.page(self.outsider, query)["items"]}
            self.assertEqual({None}, scores, query)

    def test_partial_words_match(self) -> None:
        self.make("Subscription renewal")
        self.assertEqual(["Subscription renewal"], self.titles(self.outsider, "q=subscr"))

    def test_wildcard_characters_never_reach_the_query(self) -> None:
        # Words split on anything but letters and digits, so % and _ can't
        # turn into LIKE wildcards that match every ticket
        self.make("Refund of 100 rupees")

        self.assertEqual(["Refund of 100 rupees"], self.titles(self.outsider, "q=100%25"))
        self.assertEqual(self.titles(self.outsider), self.titles(self.outsider, "q=%25%25_"))

    def test_filler_only_search_lists_everything_newest_first(self) -> None:
        self.make("Newer")
        self.assertEqual(self.titles(self.outsider), self.titles(self.outsider, "q=how+can+you"))

    def test_search_covers_resolved_tickets(self) -> None:
        self.make("Old answer", status=Ticket.Status.RESOLVED)
        self.assertEqual(["Old answer"], self.titles(self.outsider, "q=answer"))

    def test_newest_or_upvotes_overrides_relevance_while_searching(self) -> None:
        strong = self.make("Payment failed")
        weak = self.make("Help", "payment")  # newer
        strong.upvoters.add(self.outsider)

        self.assertEqual(
            ["Help", "Payment failed"], self.titles(self.outsider, "q=payment&sort=newest")
        )
        weak.upvoters.add(self.outsider, self.staff)
        self.assertEqual(
            ["Help", "Payment failed"], self.titles(self.outsider, "q=payment&sort=upvotes")
        )

    def test_status_filter_is_repeatable(self) -> None:
        self.make("Working on it", status=Ticket.Status.IN_PROGRESS)
        self.make("Done", status=Ticket.Status.RESOLVED)

        titles = self.titles(self.outsider, "status=OPN&status=PRG")

        self.assertEqual(["Working on it", "My address"], titles)

    def test_unknown_filter_values_are_rejected(self) -> None:
        for query in ("status=XYZ", "category=Nonsense", "sort=best"):
            response = self.as_user(self.outsider).get(f"/api/ticket/?{query}")
            self.assertEqual(422, response.status_code, query)

    def test_category_filter(self) -> None:
        self.make("Card declined", category=Ticket.Category.PAYMENT)
        self.assertEqual(["Card declined"], self.titles(self.outsider, "category=Payment"))

    def test_mine(self) -> None:
        self.make("Theirs", created_by=self.outsider)
        self.assertEqual(["My address"], self.titles(self.creator, "mine=true"))

    def test_upvoted_by_me(self) -> None:
        liked = self.make("Liked")
        liked.upvoters.add(self.outsider)
        self.assertEqual(["Liked"], self.titles(self.outsider, "upvoted=true"))


class TestPrivacyEverywhere(TicketTestCase):
    """Each rule the spec lists, for someone who is neither creator nor staff."""

    def setUp(self) -> None:
        super().setUp()
        self.ticket.title = "Secret refund"
        self.ticket.is_private = True
        self.ticket.save()

    def page(self, user: User, query: str = "") -> dict[str, Any]:
        response = self.as_user(user).get(f"/api/ticket/?{query}")
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def test_search_never_matches_it_even_by_exact_title(self) -> None:
        page = self.page(self.outsider, "q=Secret+refund")
        self.assertEqual(([], 0), (page["items"], page["count"]))
        self.assertEqual(1, self.page(self.creator, "q=Secret+refund")["count"])

    def test_it_is_never_counted(self) -> None:
        Ticket.objects.create(title="Public", description="-", created_by=self.creator)
        self.assertEqual(1, self.page(self.outsider)["count"])
        self.assertEqual(2, self.page(self.staff)["count"])

    def test_not_under_upvoted_after_going_private(self) -> None:
        self.ticket.upvoters.add(self.outsider)  # while it was public
        self.assertEqual([], self.page(self.outsider, "upvoted=true")["items"])

    def test_exclude_private_leaves_out_own_and_for_staff(self) -> None:
        for user in (self.creator, self.staff):
            ids = [t["id"] for t in self.page(user, "exclude_private=true")["items"]]
            self.assertNotIn(self.ticket.id, ids)

    def test_not_under_any_filter_or_sort(self) -> None:
        queries = ("category=Other", "status=OPN", "sort=upvotes", "sort=newest")
        for query in (*queries, "q=refund&sort=upvotes"):
            ids = [t["id"] for t in self.page(self.outsider, query)["items"]]
            self.assertNotIn(self.ticket.id, ids, query)


class TestCategoryValidation(TicketTestCase):
    def create(self, category: str) -> Any:
        return self.as_user(self.outsider).post(
            "/api/ticket/",
            data=json.dumps({"title": "T", "description": "D", "category": category}),
            content_type="application/json",
        )

    def test_unknown_category_is_rejected_on_create_and_update(self) -> None:
        self.assertEqual(422, self.create("Nonsense").status_code)
        self.assertEqual(422, self.put(self.staff, {"category": "Nonsense"}).status_code)

    def test_blank_category_means_none(self) -> None:
        response = self.create("")
        self.assertEqual(201, response.status_code)
        self.assertIsNone(response.json()["category"])

    def test_lowercase_other_is_normalised(self) -> None:
        Ticket.objects.filter(id=self.ticket.id).update(category="other")

        import_module("server.migrations.0163_ticket_category_case").normalise(apps, None)

        self.ticket.refresh_from_db()
        self.assertEqual("Other", self.ticket.category)
