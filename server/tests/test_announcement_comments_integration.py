"""An announcement takes reactions and comments, with one level of replies."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.announcements.models import Announcement, Comment, CommentReaction
from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server

CELEBRATE = '[data-testid="reaction-bar"] button[aria-label^="Celebrate:"]'


@pytest.mark.django_db(transaction=True)
class TestAnnouncementCommentsIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        self.player = User.objects.create_user(
            "asha@example.com", "asha@example.com", "pw", first_name="Asha", last_name="Singh"
        )
        self.post = Announcement.objects.create(
            title="Nationals",
            content="<p>Nationals in March</p>",
            author=User.objects.create(username="staff@example.com", is_staff=True),
            is_published=True,
        )

    def open_post(self, allow_comments: bool = True) -> None:
        if not allow_comments:
            Announcement.objects.filter(pk=self.post.pk).update(allow_comments=False)
        self.sign_in_as(self.player)
        self.open(f"{APP_URL}/announcement/{self.post.slug}")
        self.wait_for_element('[data-testid="reaction-bar"]', timeout=10)

    def post_comment(self, textarea: str, text: str) -> None:
        self.type(textarea, text)
        self.click(f'form:has({textarea}) button[type="submit"]')
        self.wait_for_text(text, timeout=5)

    def test_reacting_from_the_popover_and_toggling_it_off(self) -> None:
        self.open_post()
        self.assert_element_absent(CELEBRATE)
        self.click('button[aria-label="Add a reaction"]')
        self.click('button[aria-label="Celebrate"]')
        self.wait_for_element(f'{CELEBRATE}[aria-pressed="true"]', timeout=5)
        self.assert_attribute(CELEBRATE, "aria-label", "Celebrate: 1, including you")
        # Saved on the server, so a reload keeps it.
        self.refresh()
        self.wait_for_element(f'{CELEBRATE}[aria-pressed="true"]', timeout=10)
        self.click(CELEBRATE)
        self.wait_for_element_absent(CELEBRATE, timeout=5)
        self.assertFalse(self.post.reactions.exists())

    def test_commenting_replying_and_deleting(self) -> None:
        self.open_post()
        self.assert_text("No comments yet")
        self.post_comment("#new-comment", "When does registration open?")
        comment = Comment.objects.get(body="When does registration open?")
        row = f"#comment-{comment.id}"

        self.click(f'{row} button:contains("Reply")')
        self.post_comment(f"#reply-{comment.id}", "Next Monday")
        self.assert_text("Next Monday", row)  # nested under its parent

        reply = Comment.objects.get(body="Next Monday")
        self.click(f'#comment-{reply.id} button:contains("Delete")')
        self.wait_for_element_visible('dialog:contains("Delete this comment?")', timeout=3)
        self.click('dialog[open] button:contains("Delete")')
        self.wait_for_text_not_visible("Next Monday", timeout=5)
        self.assertFalse(Comment.objects.filter(pk=reply.pk).exists())

    def test_editing_a_comment(self) -> None:
        comment = Comment.objects.create(
            announcement=self.post, author=self.player, body="Registraton opens Monday"
        )
        self.open_post()
        edit = f'#comment-{comment.id} button[aria-label="Edit your comment"]'
        self.click(edit)
        self.assertEqual("Registraton opens Monday", self.get_value(f"#edit-{comment.id}"))
        self.send_keys(f"#edit-{comment.id}", "")  # Escape
        self.wait_for_element_absent(f"#edit-{comment.id}", timeout=3)

        self.click(edit)
        self.type(f"#edit-{comment.id}", "Registration opens Monday")
        self.click(f'#comment-{comment.id} button:contains("Save")')
        self.wait_for_text("Registration opens Monday", f"#comment-{comment.id}", timeout=5)
        self.assert_text("edited", f"#comment-{comment.id}")
        self.wait_for_element_absent(f"#edit-{comment.id}", timeout=3)
        comment.refresh_from_db()
        self.assertEqual("Registration opens Monday", comment.body)

    def test_comments_turned_off_hide_the_composer(self) -> None:
        Comment.objects.create(announcement=self.post, author=self.player, body="Earlier note")
        self.open_post(allow_comments=False)
        self.wait_for_text("Comments are turned off for this announcement.", timeout=5)
        self.assert_text("Earlier note")
        self.assert_element_absent("#new-comment")
        self.assert_element_absent('#comments button:contains("Reply")')

    def test_the_list_card_counts_reactions_and_comments(self) -> None:
        self.post.reactions.create(user=self.player, kind="celebrate")
        for body in ("One", "Two"):
            Comment.objects.create(announcement=self.post, author=self.player, body=body)
        self.sign_in_as(self.player)
        self.open(f"{APP_URL}/announcements")
        self.wait_for_element('[aria-label="Celebrate 1 including you, 2 comments"]', timeout=10)

    def react_to(self, comment: Comment, label: str) -> str:
        """React to a comment from its popover; the selector for that reaction's pill."""
        row = f'[data-testid="comment-reactions-{comment.id}"]'
        self.click(f'{row} button[aria-label="Add a reaction"]')
        self.click(f'{row} button[aria-label="{label}"]')
        pill = f'{row} button[aria-label^="{label}:"][aria-pressed="true"]'
        self.wait_for_element(pill, timeout=5)
        return pill

    def test_reacting_to_a_comment(self) -> None:
        comment = Comment.objects.create(
            announcement=self.post, author=self.player, body="See you there"
        )
        self.open_post()
        pill = self.react_to(comment, "Thank you")
        self.assert_attribute(pill, "aria-label", "Thank you: 1, including you")
        self.refresh()
        self.wait_for_element(pill, timeout=10)
        self.assertTrue(
            CommentReaction.objects.filter(
                comment=comment, user=self.player, kind="thanks"
            ).exists()
        )

    def test_reacting_keeps_focus_and_an_open_reply(self) -> None:
        comment = Comment.objects.create(announcement=self.post, author=self.player, body="Q")
        self.open_post()
        self.click(f'#comment-{comment.id} button:contains("Reply")')
        self.type(f"#reply-{comment.id}", "Half a thought")
        self.react_to(comment, "Like")
        # Past the save and the refetch after it, which once drew the row again.
        self.sleep(1.5)
        self.assertEqual("Half a thought", self.get_value(f"#reply-{comment.id}"))
        self.assertEqual(
            "Add a reaction",
            self.execute_script("return document.activeElement.getAttribute('aria-label')"),
        )
