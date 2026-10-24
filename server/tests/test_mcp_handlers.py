import datetime
from typing import Any

from server.announcements.models import Announcement
from server.committee.models import Committee, Role
from server.core.models import User
from server.tests.test_mcp_auth import make_token
from server.tests.test_mcp_protocol import McpProtocolTestCase
from server.utils import today


class HandlersTestCase(McpProtocolTestCase):
    bearer = "wtok"

    def setUp(self) -> None:
        super().setUp()
        make_token(self.user, "wtok", scope="hub:read hub:write")
        self.committee = Committee.objects.create(name="Helpdesk", slug="helpdesk")
        self.role(self.user, self.committee)
        self.other = User.objects.create(username="o@x.com", email="o@x.com", first_name="Om")

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

    def test_a_post_can_be_tagged(self) -> None:
        result = self.call(
            "create_announcement_draft", {"title": "MCP", "content": "Hi", "type": "tech"}
        )
        row = Announcement.objects.get(slug=result["structuredContent"]["slug"])
        self.assertEqual("tech", row.type)

        self.call("update_announcement", {"slug": row.slug, "type": "operations"})

        row.refresh_from_db()
        self.assertEqual("operations", row.type)

    def test_an_unknown_tag_is_refused(self) -> None:
        result = self.call(
            "create_announcement_draft", {"title": "MCP", "content": "Hi", "type": "gossip"}
        )

        self.assertTrue(result["isError"])
        self.assertEqual(0, Announcement.objects.count())

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
