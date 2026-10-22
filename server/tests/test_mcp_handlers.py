import datetime
from typing import Any
from unittest import mock

from server.announcements.models import Announcement
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


class TestAnnouncements(HandlersTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.committee.can_post_announcements = True
        self.committee.save()

    def test_hidden_from_non_posters(self) -> None:
        self.assertIn("create_announcement_draft", self.names(self.modern("tools/list")))
        Committee.objects.update(can_post_announcements=False)

        self.assertNotIn("create_announcement_draft", self.names(self.modern("tools/list")))

    def test_a_draft_is_unpublished_and_plain_text_becomes_escaped_paragraphs(self) -> None:
        result = self.call(
            "create_announcement_draft",
            {"title": "Trials", "content": "Line <b>one</b>\n\nLine two", "is_members_only": True},
        )

        self.assertFalse(result["isError"], result)
        row = Announcement.objects.get()
        self.assertFalse(row.is_published)
        self.assertTrue(row.is_members_only)
        self.assertEqual("<p>Line &lt;b&gt;one&lt;/b&gt;</p><p>Line two</p>", row.content)
        self.assertEqual(row.slug, result["structuredContent"]["slug"])

    def test_a_bad_button_is_refused(self) -> None:
        result = self.call(
            "create_announcement_draft",
            {"title": "Trials", "content": "Hi", "action_text": "Go"},
        )

        self.assertTrue(result["isError"])
        self.assertEqual(0, Announcement.objects.count())

    def test_publishing_asks_first(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.user)

        result = self.confirmed("publish_announcement", {"slug": row.slug})

        self.assertFalse(result["isError"], result)
        row.refresh_from_db()
        self.assertTrue(row.is_published)

    def test_publishing_shows_the_content_as_markdown(self) -> None:
        row = Announcement.objects.create(
            title="Trials",
            content="<p>Hi &amp; welcome</p><p>Bring <b>water</b></p>",
            author=self.user,
        )

        asked = self.ask("publish_announcement", {"slug": row.slug})

        text = asked["needs_confirmation"]
        self.assertIn("Trials", text)
        self.assertIn("Hi & welcome", text)
        self.assertIn("Bring **water**", text)
        self.assertNotIn("<p>", text)

    def test_a_long_draft_is_cut_in_the_question(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>" + "word " * 600 + "</p>", author=self.user
        )

        asked = self.ask("publish_announcement", {"slug": row.slug})

        self.assertLess(len(asked["needs_confirmation"]), 1800)
        self.assertIn("…", asked["needs_confirmation"])

    def test_a_draft_edited_after_the_question_asks_again(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.user)
        args = {"slug": row.slug}
        state = self.ask("publish_announcement", args)["confirmation"]
        row.content = "<p>Something else entirely</p>"
        row.save()

        result = self.call("publish_announcement", {**args, "confirmation": state})

        self.assertFalse(result["isError"])
        self.assertIn("Something changed", result["structuredContent"]["needs_confirmation"])
        row.refresh_from_db()
        self.assertFalse(row.is_published)

    def test_a_slug_with_a_path_in_it_is_refused(self) -> None:
        result = self.call("publish_announcement", {"slug": "a/../b"})

        self.assertTrue(result["isError"])
        self.assertIn("slug", result["structuredContent"]["message"])

    def test_editing_a_draft_saves_straight_away(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.user)

        result = self.call(
            "update_announcement",
            {"slug": row.slug, "title": "Open trials", "content": "Come & play\n\nBring water"},
        )

        self.assertFalse(result["isError"], result)
        row.refresh_from_db()
        self.assertEqual("Open trials", row.title)
        self.assertEqual("<p>Come &amp; play</p><p>Bring water</p>", row.content)
        self.assertFalse(row.is_published)

    def test_editing_a_published_post_asks_first_and_shows_the_change(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>Hi</p>", author=self.user, is_published=True
        )
        args = {"slug": row.slug, "content": "Moved to Sunday", "is_members_only": True}

        text = self.ask("update_announcement", args)["needs_confirmation"]
        row.refresh_from_db()
        self.assertEqual("<p>Hi</p>", row.content)
        self.assertIn("Members can already see it", text)
        self.assertIn("Moved to Sunday", text)
        self.assertIn("members only", text)

        result = self.confirmed("update_announcement", args)

        self.assertFalse(result["isError"], result)
        row.refresh_from_db()
        self.assertEqual("<p>Moved to Sunday</p>", row.content)
        self.assertTrue(row.is_members_only)

    def test_unpublishing_hides_the_post(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>Hi</p>", author=self.user, is_published=True
        )

        text = self.ask("update_announcement", {"slug": row.slug, "unpublish": True})[
            "needs_confirmation"
        ]
        result = self.confirmed("update_announcement", {"slug": row.slug, "unpublish": True})

        self.assertIn("hidden from members", text)
        self.assertFalse(result["isError"], result)
        row.refresh_from_db()
        self.assertFalse(row.is_published)

    def test_a_post_edited_after_the_question_asks_again(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>Hi</p>", author=self.user, is_published=True
        )
        args = {"slug": row.slug, "title": "Open trials"}
        state = self.ask("update_announcement", args)["confirmation"]
        row.content = "<p>Edited on Hub meanwhile</p>"
        row.save()

        result = self.call("update_announcement", {**args, "confirmation": state})

        self.assertIn("Something changed", result["structuredContent"]["needs_confirmation"])
        row.refresh_from_db()
        self.assertEqual("Trials", row.title)

    def test_the_button_can_be_removed(self) -> None:
        row = Announcement.objects.create(
            title="Trials",
            content="<p>Hi</p>",
            author=self.user,
            action_text="Sign up",
            action_url="https://example.com/form",
        )

        result = self.call(
            "update_announcement", {"slug": row.slug, "action_text": "", "action_url": ""}
        )

        self.assertFalse(result["isError"], result)
        row.refresh_from_db()
        self.assertEqual("", row.action_text or "")

    def test_a_button_without_a_link_is_refused_before_asking(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>Hi</p>", author=self.user, is_published=True
        )

        result = self.call("update_announcement", {"slug": row.slug, "action_text": "Sign up"})

        self.assertTrue(result["isError"])
        self.assertIn("needs a link", result["structuredContent"]["message"])

    def test_markdown_becomes_formatted_text_that_can_be_edited_again(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.user)

        for text in ("## When\n\n**Sunday**, 6 am", "## When\n\n**Saturday**, 6 am"):
            result = self.call("update_announcement", {"slug": row.slug, "content": text})
            self.assertFalse(result["isError"], result)

        row.refresh_from_db()
        self.assertEqual("<h2>When</h2><p><strong>Saturday</strong>, 6 am</p>", row.content)

    def test_text_with_videos_or_tables_is_left_to_hub(self) -> None:
        for content in (
            '<p>Hi</p><video src="https://x.org/v.mp4"></video>',
            "<table><tr><td>a</td></tr></table>",
        ):
            row = Announcement.objects.create(title="T", content=content, author=self.user)

            result = self.call("update_announcement", {"slug": row.slug, "content": "Plain"})

            self.assertTrue(result["isError"], content)
            row.refresh_from_db()
            self.assertEqual(content.split("<")[1][:3], row.content.split("<")[1][:3])

    def test_text_with_images_is_left_to_hub(self) -> None:
        row = Announcement.objects.create(
            title="Trials",
            content='<p>See <a href="https://example.com">the form</a></p><img src="x.png">',
            author=self.user,
        )

        refused = self.call("update_announcement", {"slug": row.slug, "content": "Plain"})
        retitled = self.call("update_announcement", {"slug": row.slug, "title": "Open trials"})

        self.assertTrue(refused["isError"])
        self.assertIn("Edit its text on Hub", refused["structuredContent"]["message"])
        self.assertFalse(retitled["isError"], retitled)
        row.refresh_from_db()
        self.assertIn("<a href", row.content)
        self.assertEqual("Open trials", row.title)

    def test_nothing_to_change_is_refused(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.user)

        result = self.call("update_announcement", {"slug": row.slug, "unpublish": False})

        self.assertTrue(result["isError"])
        self.assertIn("Nothing to change", result["structuredContent"]["message"])

    def test_editing_someone_elses_is_refused(self) -> None:
        row = Announcement.objects.create(
            title="Trials", content="<p>Hi</p>", author=self.other, is_published=True
        )

        result = self.call("update_announcement", {"slug": row.slug, "title": "Mine now"})

        self.assertTrue(result["isError"])
        self.assertIn("Not allowed", result["structuredContent"]["message"])
        row.refresh_from_db()
        self.assertEqual("Trials", row.title)

    def test_publishing_someone_elses_is_refused(self) -> None:
        row = Announcement.objects.create(title="Trials", content="<p>Hi</p>", author=self.other)

        result = self.call("publish_announcement", {"slug": row.slug})

        self.assertTrue(result["isError"])
        row.refresh_from_db()
        self.assertFalse(row.is_published)
