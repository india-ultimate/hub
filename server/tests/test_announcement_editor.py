import datetime
import io
import json
import shutil
import tempfile
from typing import Any

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from server.announcements.access import can_manage, can_post
from server.announcements.cleaning import clean_content, is_blank
from server.announcements.models import Announcement
from server.committee.models import Committee, Role
from server.core.models import Player, User
from server.task.models import Task
from server.ticket.models import Ticket
from server.utils import today

DAY = datetime.timedelta(days=1)
POST = {"title": "Trials", "content": "<p>Sunday</p>", "type": "competitions"}


def make_user(username: str, is_staff: bool = False) -> User:
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", is_staff=is_staff
    )


def png(size: tuple[int, int] = (4, 4)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, "PNG")
    return buffer.getvalue()


# A working cache, so the throttles count; cleared per test so it doesn't leak.
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class EditorTestCase(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.staff = make_user("staff", is_staff=True)
        self.poster = make_user("poster")
        self.other = make_user("other")
        self.committee = Committee.objects.create(name="Media", slug="media")
        self.role = self.give_role(self.poster)

    def give_role(self, user: User, **fields: Any) -> Role:
        fields = {"start_date": today() - 30 * DAY, **fields}
        return Role.objects.create(committee=self.committee, user=user, title="Member", **fields)

    def call(self, method: str, path: str, user: User | None = None, data: Any = None) -> Any:
        client = Client()
        if user:
            client.force_login(user)
        if data is None:
            return getattr(client, method)(f"/api/announcements{path}")
        return getattr(client, method)(
            f"/api/announcements{path}", data=json.dumps(data), content_type="application/json"
        )

    def make(self, author: User, **fields: Any) -> Announcement:
        fields = {"title": "Old", "content": "<p>x</p>", "is_published": True, **fields}
        return Announcement.objects.create(author=author, **fields)


class TestCanPost(EditorTestCase):
    def test_staff_can_post(self) -> None:
        self.assertTrue(can_post(self.staff))

    def test_a_plain_member_cannot(self) -> None:
        self.assertFalse(can_post(self.poster))
        self.assertFalse(can_post(self.other))

    def test_a_committee_switch_lets_its_people_post(self) -> None:
        Committee.objects.update(can_post_announcements=True)

        self.assertTrue(can_post(self.poster))
        self.assertFalse(can_post(self.other))

    def test_a_role_switch_lets_that_person_post(self) -> None:
        self.give_role(self.other, can_post_announcements=True)

        self.assertTrue(can_post(self.other))
        self.assertFalse(can_post(self.poster))

    def test_an_ended_term_cannot(self) -> None:
        Committee.objects.update(can_post_announcements=True)
        Role.objects.update(end_date=today())

        self.assertFalse(can_post(self.poster))

    def test_me_says_whether_the_user_can_post(self) -> None:
        Committee.objects.update(can_post_announcements=True)

        for user, expected in [(self.poster, True), (self.other, False), (self.staff, True)]:
            client = Client()
            client.force_login(user)
            self.assertEqual(expected, client.get("/api/me").json()["can_post_announcements"])


class TestCanManage(EditorTestCase):
    def setUp(self) -> None:
        super().setUp()
        Committee.objects.update(can_post_announcements=True)
        self.give_role(self.other)

    def test_a_poster_manages_their_own_only(self) -> None:
        mine, theirs = self.make(self.poster), self.make(self.other)

        self.assertTrue(can_manage(self.poster, mine))
        self.assertFalse(can_manage(self.poster, theirs))

    def test_staff_manage_any(self) -> None:
        self.assertTrue(can_manage(self.staff, self.make(self.poster)))

    def test_a_poster_who_can_no_longer_post_manages_nothing(self) -> None:
        mine = self.make(self.poster)
        Role.objects.filter(user=self.poster).update(end_date=today())

        self.assertFalse(can_manage(self.poster, mine))
        self.assertEqual(
            403, self.call("put", f"/{mine.slug}", self.poster, {"title": "x"}).status_code
        )

    def test_the_list_says_which_the_viewer_can_manage(self) -> None:
        mine, theirs = self.make(self.poster, title="Mine"), self.make(self.other, title="Theirs")

        listed = {a["slug"]: a["can_manage"] for a in self.call("get", "/", self.poster).json()}

        self.assertEqual({mine.slug: True, theirs.slug: False}, listed)


class TestDrafts(EditorTestCase):
    def test_a_draft_shows_to_its_author_and_staff_only(self) -> None:
        Committee.objects.update(can_post_announcements=True)
        self.give_role(self.other)
        draft = self.make(self.poster, is_published=False)

        for user, seen in [(self.poster, True), (self.staff, True), (self.other, False)]:
            listed = [a["slug"] for a in self.call("get", "/", user).json()]
            self.assertEqual(seen, draft.slug in listed, user)
            status = self.call("get", f"/{draft.slug}", user).status_code
            self.assertEqual(200 if seen else 404, status, user)

    def test_a_draft_of_someone_who_cannot_post_stays_hidden_from_them(self) -> None:
        draft = self.make(self.other, is_published=False)

        self.assertEqual(404, self.call("get", f"/{draft.slug}", self.other).status_code)

    def test_a_non_member_poster_uses_the_comments_of_their_members_only_draft(self) -> None:
        Committee.objects.update(can_post_announcements=True)
        draft = self.make(self.poster, is_members_only=True, is_published=False)
        client = Client()
        client.force_login(self.poster)

        self.assertEqual(200, client.get(f"/api/announcements/{draft.slug}/comments").status_code)
        self.assertEqual(
            200, client.put(f"/api/announcements/{draft.slug}/reactions/like").status_code
        )

    def test_a_poster_reads_their_own_members_only_post(self) -> None:
        Committee.objects.update(can_post_announcements=True)
        post = self.make(self.poster, is_members_only=True)

        self.assertEqual(
            "<p>x</p>", self.call("get", f"/{post.slug}", self.poster).json()["content"]
        )


class TestCleaning(TestCase):
    def test_scripts_handlers_and_javascript_links_go(self) -> None:
        html = clean_content(
            '<p onclick="x()">a</p><script>alert(1)</script><a href="javascript:x()">l</a>'
        )

        self.assertEqual('<p>a</p><a rel="noopener noreferrer">l</a>', html)

    def test_uppercase_and_encoded_javascript_links_go(self) -> None:
        for href in ("JAVASCRIPT:x()", "&#106;avascript:x()", " java\tscript:x()"):
            self.assertNotIn("href", clean_content(f'<a href="{href}">l</a>'), href)

    def test_relative_links_stay(self) -> None:
        html = '<a href="#section" rel="noopener noreferrer">s</a><a href="/tournaments" rel="noopener noreferrer">t</a>'

        self.assertEqual(html, clean_content(html))

    def test_addresses_that_leave_the_site_without_a_scheme_go(self) -> None:
        for address in ("//evil.com", " //evil.com", "\\\\evil.com", "/\\evil.com"):
            html = clean_content(f'<a href="{address}">a</a><img src="{address}">')

            self.assertNotIn("href", html, address)
            self.assertNotIn("src", html, address)

    def test_tables_and_images_stay(self) -> None:
        html = '<table><tbody><tr><td colspan="2">c</td></tr></tbody></table><img src="https://x.org/a.png" alt="a">'

        self.assertEqual(html, clean_content(html))

    def test_links_get_rel_and_only_safe_schemes_stay(self) -> None:
        html = clean_content(
            '<a href="mailto:a@b.org" target="_blank">m</a><img src="mailto:a@b.org">'
        )

        self.assertEqual(
            '<a href="mailto:a@b.org" target="_blank" rel="noopener noreferrer">m</a><img>', html
        )

    def test_an_empty_editor_is_blank_but_a_picture_is_not(self) -> None:
        self.assertTrue(is_blank("<p></p>"))
        self.assertFalse(is_blank('<p></p><img src="https://x.org/a.png">'))
        self.assertFalse(is_blank("<p>Hi</p>"))


class TestWriting(EditorTestCase):
    def setUp(self) -> None:
        super().setUp()
        Committee.objects.update(can_post_announcements=True)

    def test_a_poster_creates_a_post_in_their_name_with_clean_content(self) -> None:
        data = {**POST, "content": "<p>Hi</p><script>x</script>", "title": " Trials "}

        response = self.call("post", "/", self.poster, data)

        self.assertEqual(201, response.status_code, response.content)
        post = Announcement.objects.get()
        self.assertEqual(
            (self.poster, "Trials", "<p>Hi</p>"), (post.author, post.title, post.content)
        )
        self.assertEqual(post.slug, response.json()["slug"])
        self.assertTrue(response.json()["can_manage"])

    def test_someone_who_cannot_post_gets_403(self) -> None:
        self.assertEqual(403, self.call("post", "/", self.other, POST).status_code)
        self.assertEqual(0, Announcement.objects.count())

    def test_each_invalid_field_is_a_400(self) -> None:
        bad = [
            {"title": "  "},
            {"title": "x" * 201},
            {"content": "<script>x</script><p></p>"},
            {"action_text": "x" * 101, "action_url": "https://x.org"},
            {"action_text": "Go"},
            {"action_url": "javascript:alert(1)"},
            {"action_url": "ftp://x.org/a"},
        ]
        for change in bad:
            response = self.call("post", "/", self.poster, {**POST, **change})
            self.assertEqual(400, response.status_code, change)
            self.assertTrue(response.json()["message"], change)

    def test_a_title_without_letters_or_digits_is_a_400(self) -> None:
        for title in ("???", "!!!"):
            response = self.call("post", "/", self.poster, {**POST, "title": title})
            self.assertEqual(400, response.status_code, title)
            self.assertIn("letters or numbers", response.json()["message"])
        post = self.make(self.poster)
        response = self.call("put", f"/{post.slug}", self.poster, {"title": "???"})
        self.assertEqual(400, response.status_code)

    def test_a_title_with_control_characters_is_a_400(self) -> None:
        for title in ("Trials\nBcc: x@example.com", "Tri\x00als"):
            response = self.call("post", "/", self.poster, {**POST, "title": title})
            self.assertEqual(400, response.status_code, repr(title))

    def test_an_update_with_content_cleans_it(self) -> None:
        post = self.make(self.poster)

        self.call("put", f"/{post.slug}", self.poster, {"content": "<p>Hi</p><script>x</script>"})

        post.refresh_from_db()
        self.assertEqual("<p>Hi</p>", post.content)

    def test_a_post_the_editor_cannot_keep_can_still_be_retitled_and_published(self) -> None:
        post = self.make(self.poster, content="<video src='a.mp4'></video>", is_published=False)

        response = self.call(
            "put", f"/{post.slug}", self.poster, {"title": "New", "is_published": True}
        )

        self.assertEqual(200, response.status_code, response.content)

    def test_writes_including_deletes_share_a_limit(self) -> None:
        post = self.make(self.poster)
        for _ in range(30):
            self.call("put", f"/{post.slug}", self.poster, {"title": "x"})

        self.assertEqual(429, self.call("delete", f"/{post.slug}", self.poster).status_code)

    def test_an_unknown_type_is_refused(self) -> None:
        self.assertEqual(
            422, self.call("post", "/", self.poster, {**POST, "type": "nope"}).status_code
        )

    def test_a_button_with_a_link_is_kept(self) -> None:
        data = {**POST, "action_text": "Sign up", "action_url": "https://x.org/s"}

        response = self.call("post", "/", self.poster, data)

        self.assertEqual(
            ("Sign up", "https://x.org/s"),
            (response.json()["action_text"], response.json()["action_url"]),
        )

    def test_an_update_changes_only_what_is_sent(self) -> None:
        post = self.make(self.poster, title="Old", is_members_only=True)

        response = self.call(
            "put", f"/{post.slug}", self.poster, {"title": "New", "is_published": False}
        )

        self.assertEqual(200, response.status_code, response.content)
        post.refresh_from_db()
        self.assertEqual(
            ("New", "<p>x</p>", True, False),
            (post.title, post.content, post.is_members_only, post.is_published),
        )
        self.assertEqual("old", post.slug)

    def test_a_title_edit_leaves_old_content_the_editor_cannot_keep(self) -> None:
        post = self.make(self.poster, content='<p style="color:red">x</p>')

        self.call("put", f"/{post.slug}", self.poster, {"title": "New"})

        post.refresh_from_db()
        self.assertEqual('<p style="color:red">x</p>', post.content)

    def test_an_update_is_validated_too(self) -> None:
        post = self.make(self.poster)

        self.assertEqual(
            400, self.call("put", f"/{post.slug}", self.poster, {"title": ""}).status_code
        )
        self.assertEqual(
            400, self.call("put", f"/{post.slug}", self.poster, {"action_text": "Go"}).status_code
        )

    def test_updating_and_deleting_follow_who_can_manage(self) -> None:
        post = self.make(self.poster)
        self.give_role(self.other)

        self.assertEqual(404, self.call("put", "/nope", self.poster, {"title": "x"}).status_code)
        self.assertEqual(
            403, self.call("put", f"/{post.slug}", self.other, {"title": "x"}).status_code
        )
        self.assertEqual(403, self.call("delete", f"/{post.slug}", self.other).status_code)
        self.assertEqual(204, self.call("delete", f"/{post.slug}", self.poster).status_code)
        self.assertEqual(0, Announcement.objects.count())

    def test_staff_delete_any_post(self) -> None:
        post = self.make(self.poster)

        self.assertEqual(204, self.call("delete", f"/{post.slug}", self.staff).status_code)

    def test_a_draft_hidden_from_a_user_is_a_404_not_a_403(self) -> None:
        draft = self.make(self.poster, is_published=False)

        self.assertEqual(404, self.call("delete", f"/{draft.slug}", self.other).status_code)


class TestImages(EditorTestCase):
    def setUp(self) -> None:
        super().setUp()
        Committee.objects.update(can_post_announcements=True)
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)

    def upload(self, user: User, name: str = "pic.png", content: bytes | None = None) -> Any:
        client = Client()
        client.force_login(user)
        file = SimpleUploadedFile(name, png() if content is None else content)
        return client.post("/api/announcements/images", {"file": file})

    def test_a_poster_uploads_a_picture_and_gets_its_url(self) -> None:
        response = self.upload(self.poster)

        self.assertEqual(200, response.status_code, response.content)
        url = response.json()["url"]
        self.assertIn("announcement_images/", url)
        self.assertTrue(url.endswith(".png"))
        self.assertNotIn("pic", url)

    def test_an_uploaded_picture_survives_cleaning(self) -> None:
        url = self.upload(self.poster).json()["url"]
        html = f'<img src="{url}">'

        self.assertEqual(html, clean_content(html))

    def test_someone_who_cannot_post_gets_403(self) -> None:
        self.assertEqual(403, self.upload(self.other).status_code)

    def test_a_file_that_is_not_an_image_is_refused(self) -> None:
        self.assertEqual(400, self.upload(self.poster, content=b"<script>x</script>").status_code)
        self.assertEqual(400, self.upload(self.poster, name="a.html").status_code)

    def test_uploads_are_limited(self) -> None:
        for _ in range(30):
            self.assertEqual(200, self.upload(self.poster).status_code)

        self.assertEqual(429, self.upload(self.poster).status_code)

    def test_an_oversized_file_is_refused(self) -> None:
        response = self.upload(self.poster, content=png() + b"0" * (10 * 1024 * 1024))

        self.assertEqual(400, response.status_code)
        self.assertIn("10 MB", response.json()["message"])


class TestEmails(EditorTestCase):
    def setUp(self) -> None:
        super().setUp()
        Committee.objects.update(can_post_announcements=True)
        self.post = self.make(self.poster)
        for user in (self.poster, self.other):
            Player.objects.create(user=user, date_of_birth="1990-01-01")

    def send(self, user: User, audience: str = "all") -> Any:
        return self.call("post", f"/{self.post.slug}/email", user, {"audience": audience})

    def test_staff_email_all_users_or_members(self) -> None:
        response = self.send(self.staff)

        self.assertEqual((200, {"queued": 2}), (response.status_code, response.json()))
        self.assertEqual({"queued": 0}, self.send(self.staff, "members").json())

    def test_a_poster_cannot_email_everyone_even_for_their_own_post(self) -> None:
        for audience in ("all", "members"):
            self.assertEqual(403, self.send(self.poster, audience).status_code)
        self.assertEqual(0, Task.objects.count())

    def test_an_unpublished_post_cannot_be_emailed(self) -> None:
        Announcement.objects.update(is_published=False)

        self.assertEqual(400, self.send(self.staff).status_code)

    def test_a_test_email_goes_to_the_requester_only(self) -> None:
        response = self.call("post", f"/{self.post.slug}/email/test", self.poster, {})

        self.assertEqual((200, {"queued": 1}), (response.status_code, response.json()))
        self.assertEqual([[self.poster.email]], [t.data["to"] for t in Task.objects.all()])

    def test_emails_are_limited(self) -> None:
        for _ in range(10):
            self.assertEqual(
                200, self.call("post", f"/{self.post.slug}/email/test", self.poster, {}).status_code
            )

        self.assertEqual(
            429, self.call("post", f"/{self.post.slug}/email/test", self.poster, {}).status_code
        )

    def test_a_test_email_needs_the_right_to_manage(self) -> None:
        self.assertEqual(
            403, self.call("post", f"/{self.post.slug}/email/test", self.other, {}).status_code
        )


class TestDeleteCommittee(EditorTestCase):
    def delete(self, user: User) -> Any:
        client = Client()
        client.force_login(user)
        return client.delete(f"/api/committees/{self.committee.slug}")

    def test_only_staff_can_delete(self) -> None:
        self.assertEqual(403, self.delete(self.poster).status_code)
        self.assertTrue(Committee.objects.filter(pk=self.committee.pk).exists())

    def test_it_takes_its_roles_and_routes_but_not_tickets(self) -> None:
        self.committee.routes.create(category_id="Other")
        ticket = Ticket.objects.create(
            title="t", description="d", created_by=self.other, category_id="Other"
        )

        self.assertEqual(204, self.delete(self.staff).status_code)

        self.assertFalse(Committee.objects.filter(pk=self.committee.pk).exists())
        self.assertEqual(0, Role.objects.filter(user=self.poster).count())
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_an_update_leaves_the_switch_unless_it_is_sent(self) -> None:
        Committee.objects.update(can_post_announcements=True)
        client = Client()
        client.force_login(self.staff)

        response = client.put(
            f"/api/committees/{self.committee.slug}",
            data=json.dumps({"name": "Media team"}),
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["can_post_announcements"])

    def test_a_role_update_leaves_the_switch_unless_it_is_sent(self) -> None:
        Role.objects.update(can_post_announcements=True)
        client = Client()
        client.force_login(self.staff)

        response = client.put(
            f"/api/committees/roles/{self.role.id}",
            data=json.dumps({"title": "Chair"}),
            content_type="application/json",
        )

        self.assertTrue(response.json()["can_post_announcements"])

    def test_a_missing_committee_is_a_404(self) -> None:
        self.committee.delete()

        self.assertEqual(404, self.delete(self.staff).status_code)
