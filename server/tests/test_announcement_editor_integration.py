"""Writing announcements in the Hub: the editor, the email panel and the committee switches."""

import datetime
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PIL import Image
from seleniumbase import BaseCase

from server.announcements.models import Announcement
from server.committee.models import Committee, Role
from server.core.models import User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.utils import today

EDITOR = ".ProseMirror"


@pytest.mark.django_db(transaction=True)
class TestAnnouncementEditorIntegration(BaseCase):
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
        self.staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )
        self.meera = User.objects.create_user(
            "meera@example.com", "meera@example.com", "pw", first_name="Meera", last_name="Rao"
        )
        self.zonal = Committee.objects.create(
            name="Zonal", slug="zonal", order=99, can_post_announcements=True
        )
        Role.objects.create(
            committee=self.zonal,
            user=self.meera,
            title="Chair",
            is_chair=True,
            start_date=today() - datetime.timedelta(days=30),
        )

    def publish_as_meera(self) -> Announcement:
        return Announcement.objects.create(
            title="Zonal dates",
            content="<p>See you there</p>",
            author=self.meera,
            is_published=True,
        )

    def test_a_chair_writes_saves_a_draft_publishes_and_edits_a_post(self) -> None:
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcements")
        self.click('a:contains("New announcement")')
        self.type("#announcement-title", "Zonal dates")
        self.click(EDITOR)
        self.click('button[aria-label="Bold"]')
        self.send_keys(EDITOR, "Bold start")
        self.click('button[aria-label="Bold"]')
        self.send_keys(EDITOR, " then plain")
        self.click('button[aria-label="Bulleted list"]')
        self.send_keys(EDITOR, "\none\ntwo")

        self.click('button:contains("Save draft")')
        self.wait_for_element('button:contains("Publish")', timeout=10)
        self.wait_for_element("#email-heading", timeout=10)  # the post exists now
        post = Announcement.objects.get(title="Zonal dates")
        self.assertFalse(post.is_published)
        self.assertEqual(post.author, self.meera)
        self.assertIn("<strong>Bold start</strong>", post.content)
        self.assertIn("<li>", post.content)

        self.click('button:contains("Publish")')
        self.click('dialog[open] button:contains("Publish")')
        self.wait_for_text("Zonal dates", "h1", timeout=10)
        post.refresh_from_db()
        self.assertTrue(post.is_published)

        self.click('a:contains("Edit")')
        self.type("#announcement-title", "Zonal dates, updated")
        self.click('button:contains("Save changes")')
        self.wait_for_text("Saved", timeout=10)
        post.refresh_from_db()
        self.assertEqual(post.title, "Zonal dates, updated")
        self.assertTrue(post.is_published)

    def test_only_staff_see_the_buttons_that_email_everyone(self) -> None:
        post = self.publish_as_meera()
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/announcement/{post.slug}/edit")
        self.wait_for_element("#email-heading", timeout=10)
        self.assert_element('button:contains("Send to all users")')
        self.assert_element('button:contains("Send to members")')

        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcement/{post.slug}/edit")
        self.wait_for_element("#email-heading", timeout=10)
        self.assert_element('button:contains("Send a test to me")')
        self.assert_element_absent('button:contains("Send to all users")')
        self.assert_element_absent('button:contains("Send to members")')

    def test_staff_switch_on_a_committees_posting_and_delete_a_committee(self) -> None:
        self.zonal.can_post_announcements = False
        self.zonal.save()
        form = "form:has(#zonal-name)"
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/committees/manage")
        self.click("#committees-tab")
        self.js_click(f'{form} input[role="switch"]')
        self.wait_for_text("Saved", timeout=10)
        self.zonal.refresh_from_db()
        self.assertTrue(self.zonal.can_post_announcements)

        self.click(f'{form} button:contains("Delete committee")')
        self.wait_for_text("1 current and 0 past roles", "dialog[open]", timeout=10)
        self.click('dialog[open] button:contains("Delete committee")')
        self.wait_for_element_absent("#zonal-name", timeout=10)
        self.assertFalse(Committee.objects.filter(slug="zonal").exists())

    def test_applying_a_link_does_not_save_the_post(self) -> None:
        post = self.publish_as_meera()
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcement/{post.slug}/edit")
        self.wait_for_element("#announcement-title", timeout=10)
        self.click(EDITOR)
        self.send_keys(EDITOR, " unreviewed")
        self.click('button[aria-label="Link"]')
        self.type("#link-url", "https://example.com/dates")
        self.click('button:contains("Apply")')
        self.wait_for_element_absent("#link-url", timeout=5)
        self.assert_element(f'{EDITOR} a[href="https://example.com/dates"]')
        self.sleep(1)
        post.refresh_from_db()
        self.assertEqual(post.content, "<p>See you there</p>")

    def test_an_uploaded_image_takes_a_description(self) -> None:
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcements/new")
        self.type("#announcement-title", "Photos")
        self.click(EDITOR)
        self.send_keys(EDITOR, "Look")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "team.png"
            Image.new("RGB", (20, 20), "blue").save(path)
            self.choose_file("#image-file", str(path))
            # The browser reads the file as it uploads: keep it until then.
            self.wait_for_element("#image-alt", timeout=10)
        self.type("#image-alt", "Team photo")
        self.click('button:contains("Save draft")')
        self.wait_for_element("#email-heading", timeout=10)
        self.assertIn('alt="Team photo"', Announcement.objects.get(title="Photos").content)

    def test_someone_who_cannot_post_is_refused(self) -> None:
        asha = User.objects.create_user("asha@example.com", "asha@example.com", "pw")
        self.sign_in_as(asha)
        self.open(f"{APP_URL}/announcements/new")
        self.wait_for_text("you do not have access", timeout=10)
        self.assert_element_absent("#announcement-title")

    def test_a_post_with_formatting_the_editor_would_drop_shows_a_notice_first(self) -> None:
        post = self.publish_as_meera()
        post.content = '<p style="color:red">Hi</p><video src="https://example.com/a.mp4"></video>'
        post.save()
        self.sign_in_as(self.staff)
        self.open(f"{APP_URL}/announcement/{post.slug}/edit")
        self.wait_for_text("formatting the Hub editor can't keep", timeout=10)
        self.assert_element(f'a[href="/admin/server/announcement/{post.id}/change/"]')
        self.assert_element_absent("#announcement-title")
        self.click('button:contains("Continue here")')
        self.wait_for_element("#announcement-title", timeout=5)

    def test_leaving_with_unsaved_changes_asks_first(self) -> None:
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcements/new")
        self.type("#announcement-title", "Half written")
        self.click('a:contains("Back")')
        self.wait_for_text("Leave without saving?", "dialog[open]", timeout=5)
        self.click('dialog[open] button:contains("Cancel")')
        self.assert_element("#announcement-title")
        self.click('a:contains("Back")')
        self.click('dialog[open] button:contains("Leave")')
        self.wait_for_text("Announcements", "h1", timeout=10)
        self.assertFalse(Announcement.objects.filter(title="Half written").exists())

    def test_each_image_keeps_its_own_description(self) -> None:
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcements/new")
        self.type("#announcement-title", "Two photos")
        self.click(EDITOR)
        self.send_keys(EDITOR, "Look")
        with TemporaryDirectory() as folder:
            for name, alt in (("a.png", "First"), ("b.png", "Second")):
                path = Path(folder) / name
                Image.new("RGB", (20, 20), "blue").save(path)
                before = len(self.find_elements(f"{EDITOR} img"))
                self.choose_file("#image-file", str(path))
                self.wait_for_element(f"{EDITOR} img.ProseMirror-selectednode", timeout=10)
                for _ in range(20):
                    if len(self.find_elements(f"{EDITOR} img")) > before:
                        break
                    self.sleep(0.5)
                self.assert_equal(self.get_value("#image-alt"), "")
                self.type("#image-alt", alt)
        self.find_elements(f"{EDITOR} img")[0].click()
        self.assert_equal(self.get_value("#image-alt"), "First")
        self.click('button:contains("Save draft")')
        self.wait_for_element("#email-heading", timeout=10)
        content = Announcement.objects.get(title="Two photos").content
        self.assertIn('alt="First"', content)
        self.assertIn('alt="Second"', content)

    def test_an_uploaded_video_goes_in_the_post(self) -> None:
        self.sign_in_as(self.meera)
        self.open(f"{APP_URL}/announcements/new")
        self.type("#announcement-title", "How to merge accounts")
        self.click(EDITOR)
        self.send_keys(EDITOR, "Watch")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "merge.mp4"
            path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
            self.choose_file("#video-file", str(path))
            # The browser reads the file as it uploads: keep it until then.
            self.wait_for_element(f"{EDITOR} video", timeout=10)
        self.click('button:contains("Save draft")')
        self.wait_for_element("#email-heading", timeout=10)
        content = Announcement.objects.get(title="How to merge accounts").content
        self.assertIn("<video", content)
        self.assertIn("announcement_videos/", content)
        self.assertIn("controls", content)
