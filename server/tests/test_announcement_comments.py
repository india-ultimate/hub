import json
from typing import Any

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from server.announcements.models import Announcement, Comment, CommentReaction, Reaction
from server.core.models import Player, User

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


# A working cache, so the comment throttle counts; cleared per test so it doesn't leak.
@override_settings(CACHES=LOCMEM)
class AnnouncementCommentsTestCase(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.staff = User.objects.create(
            username="staff@example.com", email="staff@example.com", is_staff=True
        )
        self.post = Announcement.objects.create(
            title="Nationals", content="<p>In March</p>", author=self.staff, is_published=True
        )
        self.user = self._user("reader@example.com", "Asha")
        self.other = self._user("other@example.com", "Ravi")
        self.client.force_login(self.user)

    def _user(self, email: str, first_name: str) -> User:
        user = User.objects.create(username=email, email=email, first_name=first_name)
        Player.objects.create(user=user, date_of_birth="1990-01-01")
        return user

    def test_an_author_with_a_photo_shows_it_on_the_post_and_the_comment(self) -> None:
        Player.objects.filter(user=self.user).update(profile_pic_url="https://x.org/a.jpg")
        self._post("Hello")

        announcement = self.client.get(f"/api/announcements/{self.post.slug}").json()
        self.post.author = self.user
        self.post.save()
        authored = self.client.get(f"/api/announcements/{self.post.slug}").json()

        self.assertIsNone(announcement["author_profile_pic_url"])
        self.assertEqual("https://x.org/a.jpg", authored["author_profile_pic_url"])
        self.assertEqual("https://x.org/a.jpg", self._comments()[0]["author_profile_pic_url"])

    def _as(self, user: User) -> None:
        self.client.force_login(user)

    def _comments(self, slug: str | None = None) -> list[dict[str, Any]]:
        response = self.client.get(f"/api/announcements/{slug or self.post.slug}/comments")
        self.assertEqual(200, response.status_code, response.content)
        data: list[dict[str, Any]] = response.json()
        return data

    def _post(self, body: str, parent_id: int | None = None, slug: str | None = None) -> Any:
        return self.client.post(
            f"/api/announcements/{slug or self.post.slug}/comments",
            {"body": body, "parent_id": parent_id},
            content_type="application/json",
        )

    def _comment(self, body: str, parent_id: int | None = None) -> int:
        response = self._post(body, parent_id)
        self.assertEqual(201, response.status_code, response.content)
        comment_id: int = response.json()["id"]
        return comment_id

    def _delete(self, comment_id: int) -> Any:
        return self.client.delete(f"/api/announcements/comments/{comment_id}")

    def _react(self, kind: str, method: str = "put", slug: str | None = None) -> Any:
        url = f"/api/announcements/{slug or self.post.slug}/reactions/{kind}"
        return getattr(self.client, method)(url)

    def _react_to(self, comment_id: int, kind: str, method: str = "put") -> Any:
        url = f"/api/announcements/comments/{comment_id}/reactions/{kind}"
        return getattr(self.client, method)(url)

    def _detail(self) -> dict[str, Any]:
        data: dict[str, Any] = self.client.get(f"/api/announcements/{self.post.slug}").json()
        return data

    # Reactions

    def test_put_adds_a_reaction_once(self) -> None:
        for _ in range(2):
            response = self._react("celebrate")
            self.assertEqual(200, response.status_code, response.content)
            self.assertEqual([{"kind": "celebrate", "count": 1, "reacted": True}], response.json())
        self.assertEqual(1, Reaction.objects.count())

    def test_delete_removes_a_reaction(self) -> None:
        self._react("like")
        response = self._react("like", "delete")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())
        self.assertFalse(Reaction.objects.exists())

    def test_several_kinds_per_user_in_kind_order(self) -> None:
        self._react("dislike")
        response = self._react("like")
        self.assertEqual(["like", "dislike"], [r["kind"] for r in response.json()])

    def test_unknown_kind_is_422(self) -> None:
        self.assertEqual(422, self._react("angry").status_code)
        self.assertEqual(422, self._react("angry", "delete").status_code)

    def test_counts_and_reacted_in_list_and_detail(self) -> None:
        self._react("love")
        self._react("thanks")
        self._as(self.other)
        self._react("love")
        expected = [
            {"kind": "love", "count": 2, "reacted": True},
            {"kind": "thanks", "count": 1, "reacted": False},
        ]
        self.assertEqual(expected, self._detail()["reactions"])
        listed = {a["slug"]: a for a in self.client.get("/api/announcements/").json()}
        self.assertEqual(expected, listed[self.post.slug]["reactions"])
        self.assertTrue(listed[self.post.slug]["allow_comments"])

    def test_locked_post_is_403_and_shows_no_reactions_or_count(self) -> None:
        self.post.is_members_only = True
        self.post.save()
        Reaction.objects.create(announcement=self.post, user=self.staff, kind="like")
        Comment.objects.create(announcement=self.post, author=self.staff, body="Members!")
        locked = {"message": "This announcement is for members only."}
        for response in (
            self._react("like"),
            self._react("like", "delete"),
            self.client.get(f"/api/announcements/{self.post.slug}/comments"),
            self._post("Hello"),
        ):
            self.assertEqual(403, response.status_code)
            self.assertEqual(locked, response.json())
        detail = self._detail()
        self.assertEqual(([], 0), (detail["reactions"], detail["comment_count"]))
        comment = Comment.objects.get()
        self.assertEqual(403, self._delete(comment.id).status_code)
        self.assertTrue(Comment.objects.exists())

    def test_draft_is_404_for_non_staff(self) -> None:
        self.post.is_published = False
        self.post.save()
        comment = Comment.objects.create(announcement=self.post, author=self.user, body="Hi")
        self.assertEqual(404, self._react("like").status_code)
        self.assertEqual(404, self._post("Hello").status_code)
        self.assertEqual(404, self._delete(comment.id).status_code)
        self.assertEqual(404, self._react("like", slug="no-such-post").status_code)

    # Comments

    def test_post_and_list_oldest_first_with_replies_nested(self) -> None:
        first = self._comment("When is it?")
        self._as(self.staff)
        answer = self._comment("  In March.\nSee you there  ", first)
        second = self._comment("Bring water")

        comments = self._comments()

        self.assertEqual([first, second], [c["id"] for c in comments])
        self.assertEqual([answer], [r["id"] for r in comments[0]["replies"]])
        reply = comments[0]["replies"][0]
        self.assertEqual("In March.\nSee you there", reply["body"])
        self.assertTrue(reply["author_is_staff"])
        self.assertEqual([], reply["replies"])
        self.assertEqual("Asha", comments[0]["author"]["first_name"])
        self.assertFalse(comments[0]["author_is_staff"])

    def test_reply_to_a_reply_joins_the_thread(self) -> None:
        top = self._comment("Question")
        reply = self._comment("Answer", top)
        response = self._post("Thanks", reply)
        self.assertEqual(201, response.status_code)
        self.assertEqual(top, Comment.objects.get(pk=response.json()["id"]).parent_id)
        self.assertEqual(2, len(self._comments()[0]["replies"]))

    def test_empty_or_too_long_body_is_400(self) -> None:
        for body in ("   ", "x" * 2001):
            response = self._post(body)
            self.assertEqual(400, response.status_code)
            self.assertIn("message", response.json())
        self.assertEqual(201, self._post("x" * 2000).status_code)

    def test_comments_turned_off_refuses_new_ones_but_still_lists(self) -> None:
        self._comment("Before")
        self.post.allow_comments = False
        self.post.save()
        response = self._post("After")
        self.assertEqual(403, response.status_code)
        self.assertEqual(
            {"message": "Comments are turned off for this announcement."}, response.json()
        )
        self.assertEqual(["Before"], [c["body"] for c in self._comments()])
        self.assertFalse(self._detail()["allow_comments"])

    def test_parent_from_another_post_or_deleted_is_400(self) -> None:
        other_post = Announcement.objects.create(
            title="Other", content="<p>x</p>", author=self.staff, is_published=True
        )
        elsewhere = Comment.objects.create(announcement=other_post, author=self.user, body="Hi")
        self.assertEqual(400, self._post("Reply", elsewhere.id).status_code)
        deleted = Comment.objects.create(
            announcement=self.post, author=self.user, body="", is_deleted=True
        )
        self.assertEqual(400, self._post("Reply", deleted.id).status_code)

    def test_who_may_delete(self) -> None:
        mine = self._comment("Mine")
        theirs = self._comment("Also mine")
        self._as(self.other)
        self.assertFalse(self._comments()[0]["can_delete"])
        response = self._delete(mine)
        self.assertEqual(403, response.status_code)
        self.assertIn("message", response.json())

        self._as(self.user)
        self.assertTrue(self._comments()[0]["can_delete"])
        self.assertEqual(204, self._delete(mine).status_code)
        self._as(self.staff)
        self.assertTrue(self._comments()[0]["can_delete"])
        self.assertEqual(204, self._delete(theirs).status_code)
        self.assertFalse(Comment.objects.exists())
        self.assertEqual(404, self._delete(theirs).status_code)

    def test_deleting_with_replies_soft_deletes_and_last_reply_removes_both(self) -> None:
        top = self._comment("Question")
        reply = self._comment("Answer", top)
        lone = self._comment("Lone")

        self._delete(top)
        self._delete(lone)

        comments = self._comments()
        self.assertEqual([top], [c["id"] for c in comments])
        self.assertTrue(comments[0]["is_deleted"])
        self.assertEqual("", comments[0]["body"])
        self.assertFalse(comments[0]["can_delete"])
        self.assertEqual([reply], [r["id"] for r in comments[0]["replies"]])
        self.assertEqual(1, self._detail()["comment_count"])

        self._delete(reply)
        self.assertFalse(Comment.objects.exists())

    def test_comment_count_leaves_out_deleted_comments(self) -> None:
        top = self._comment("Question")
        self._comment("Answer", top)
        self._comment("Another")
        self.assertEqual(3, self._detail()["comment_count"])
        self._delete(top)
        self.assertEqual(2, self._detail()["comment_count"])

    def test_no_emails_in_comments(self) -> None:
        top = self._comment("Question")
        self._as(self.staff)
        self._comment("Answer", top)
        body = json.dumps(self._comments())
        self.assertNotIn("email", body)
        self.assertNotIn("@example.com", body)

    def test_eleventh_comment_in_a_minute_is_throttled(self) -> None:
        for i in range(10):
            self.assertEqual(201, self._post(f"Comment {i}").status_code)
        self.assertEqual(429, self._post("One more").status_code)
        # Per user: someone else can still comment.
        self._as(self.other)
        self.assertEqual(201, self._post("Mine").status_code)

    def test_reactions_have_their_own_limit(self) -> None:
        for _ in range(30):
            self.assertEqual(200, self._react("like").status_code)
        # Reacting doesn't use up the comment limit.
        self.assertEqual(201, self._post("Still here").status_code)
        for _ in range(30):
            self._react("like")
        self.assertEqual(429, self._react("like").status_code)

    # Comment reactions

    def test_reacting_to_a_comment_and_a_reply(self) -> None:
        top = self._comment("When is it?")
        reply = self._comment("March", parent_id=top)
        self.assertEqual(
            [{"kind": "celebrate", "count": 1, "reacted": True}],
            self._react_to(reply, "celebrate").json(),
        )
        self._react_to(reply, "celebrate")  # twice is still once
        self._react_to(top, "like")
        self._as(self.other)
        self._react_to(top, "like")
        self._react_to(top, "thanks")

        (comment,) = self._comments()
        self.assertEqual(
            [
                {"kind": "like", "count": 2, "reacted": True},
                {"kind": "thanks", "count": 1, "reacted": True},
            ],
            comment["reactions"],
        )
        self.assertEqual(
            [{"kind": "celebrate", "count": 1, "reacted": False}],
            comment["replies"][0]["reactions"],
        )
        self.assertEqual(
            [{"kind": "like", "count": 2, "reacted": True}],
            self._react_to(top, "thanks", "delete").json(),
        )

    def test_a_new_comment_has_no_reactions(self) -> None:
        self.assertEqual([], self._post("Hi").json()["reactions"])

    def test_deleted_or_unknown_comment_takes_no_reaction(self) -> None:
        top = self._comment("Q")
        self._react_to(top, "like")
        self._comment("A", parent_id=top)
        self._delete(top)  # kept, as deleted, for its reply
        for comment_id in (top, 999999):
            response = self._react_to(comment_id, "love")
            self.assertEqual(404, response.status_code)
            self.assertEqual({"message": "Comment not found"}, response.json())
        self.assertEqual([], self._comments()[0]["reactions"])

    def test_comment_reactions_on_a_locked_or_draft_post(self) -> None:
        comment = Comment.objects.create(announcement=self.post, author=self.staff, body="Hi")
        self.post.is_members_only = True
        self.post.save()
        for method in ("put", "delete"):
            response = self._react_to(comment.id, "like", method)
            self.assertEqual(403, response.status_code)
        self.post.is_members_only, self.post.is_published = False, False
        self.post.save()
        self.assertEqual(404, self._react_to(comment.id, "like").status_code)
        self.assertFalse(CommentReaction.objects.exists())

    def test_comment_reactions_have_their_own_limit(self) -> None:
        comment = self._comment("Hi")
        for _ in range(30):
            self.assertEqual(200, self._react_to(comment, "like").status_code)
            self.assertEqual(200, self._react_to(comment, "like", "delete").status_code)
        self.assertEqual(429, self._react_to(comment, "like").status_code)
        # Reacting to comments doesn't use up the limit for reacting to posts.
        self.assertEqual(200, self._react("like").status_code)

    def test_list_queries_do_not_grow_with_announcements(self) -> None:
        def seed() -> None:
            post = Announcement.objects.create(
                title="Post", content="<p>x</p>", author=self.staff, is_published=True
            )
            Reaction.objects.create(announcement=post, user=self.other, kind="like")
            Comment.objects.create(announcement=post, author=self.other, body="Hi")

        def queries() -> int:
            with CaptureQueriesContext(connection) as context:
                self.assertEqual(200, self.client.get("/api/announcements/").status_code)
            return len(context)

        self.post.delete()
        seed()
        one = queries()
        seed()
        seed()
        with self.assertNumQueries(one):
            self.assertEqual(3, len(self.client.get("/api/announcements/").json()))

    def test_comment_queries_do_not_grow_with_comments(self) -> None:
        def seed() -> None:
            top = Comment.objects.create(announcement=self.post, author=self.other, body="Q")
            reply = Comment.objects.create(
                announcement=self.post, author=self.staff, body="A", parent=top
            )
            for comment in (top, reply):
                CommentReaction.objects.create(comment=comment, user=self.other, kind="like")

        def queries() -> int:
            with CaptureQueriesContext(connection) as context:
                self._comments()
            return len(context)

        seed()
        one = queries()
        seed()
        seed()
        with self.assertNumQueries(one):
            self._comments()
