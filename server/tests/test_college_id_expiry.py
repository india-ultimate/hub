"""College ID images go 30 days after the card expires; the row stays."""

import datetime
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test.client import MULTIPART_CONTENT

from server.core.models import CollegeId
from server.tests.base import ApiBaseTestCase
from server.utils import today


class TestRemoveExpiredCollegeIds(ApiBaseTestCase):
    def card(self, days_past_expiry: int) -> CollegeId:
        return CollegeId.objects.create(
            player=self.player,
            expiry=today() - datetime.timedelta(days=days_past_expiry),
            card_front="college_ids/f.jpg",
            card_back="college_ids/b.jpg",
        )

    def run_command(self, *args: str) -> tuple[str, mock.MagicMock]:
        out = StringIO()
        with mock.patch("django.core.files.storage.FileSystemStorage.delete") as delete:
            call_command("remove_expired_college_ids", *args, stdout=out)
        return out.getvalue(), delete

    def test_day_30_keeps_day_31_clears(self) -> None:
        card = self.card(30)
        self.run_command()
        card.refresh_from_db()
        self.assertIsNone(card.images_removed_at)
        CollegeId.objects.filter(pk=card.pk).update(expiry=today() - datetime.timedelta(days=31))
        _, delete = self.run_command()
        card.refresh_from_db()
        self.assertEqual(today(), card.images_removed_at)
        self.assertEqual(("", ""), (card.card_front.name, card.card_back.name))
        self.assertEqual(2, delete.call_count)
        self.assertTrue(CollegeId.objects.filter(pk=card.pk).exists())  # the row stays

    def test_dry_run_changes_nothing(self) -> None:
        card = self.card(40)
        out, delete = self.run_command("--dry-run")
        delete.assert_not_called()
        card.refresh_from_db()
        self.assertIsNone(card.images_removed_at)
        self.assertIn("1 to clear", out)

    def test_a_failed_delete_leaves_the_row(self) -> None:
        card = self.card(40)
        out = StringIO()
        with mock.patch(
            "django.core.files.storage.FileSystemStorage.delete", side_effect=OSError("down")
        ):
            call_command("remove_expired_college_ids", stdout=out)
        card.refresh_from_db()
        self.assertIsNone(card.images_removed_at)
        self.assertEqual("college_ids/f.jpg", card.card_front.name)
        self.assertIn("failed", out.getvalue())

    def test_reuploading_makes_the_card_active_again(self) -> None:
        card = self.card(40)
        self.run_command()
        self.client.force_login(self.user)
        expiry = str(today() + datetime.timedelta(days=365))
        response = self.client.post(
            "/api/college-id",
            data={
                "college_id": f'{{"player_id": {self.player.id}, "expiry": "{expiry}"}}',
                "card_front": SimpleUploadedFile("f.jpg", b"f", content_type="image/jpeg"),
                "card_back": SimpleUploadedFile("b.jpg", b"b", content_type="image/jpeg"),
            },
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["images_removed_at"])
        # Still a URL, not the bare file name, now the schema allows empty cards.
        self.assertTrue(response.json()["card_front"].startswith(settings.MEDIA_URL))
        card.refresh_from_db()
        self.assertIsNone(card.images_removed_at)
        self.run_command()
        card.refresh_from_db()
        self.assertIsNone(card.images_removed_at)  # not expired, so the job leaves it

    def test_reuploading_deletes_the_old_card(self) -> None:
        # Nothing else would: the old scans would stay public for good.
        self.card(-10)
        self.client.force_login(self.user)
        expiry = str(today() + datetime.timedelta(days=365))
        with mock.patch("django.core.files.storage.FileSystemStorage.delete") as delete:
            response = self.client.post(
                "/api/college-id",
                data={
                    "college_id": f'{{"player_id": {self.player.id}, "expiry": "{expiry}"}}',
                    "card_front": SimpleUploadedFile("f2.jpg", b"f", content_type="image/jpeg"),
                    "card_back": SimpleUploadedFile("b2.jpg", b"b", content_type="image/jpeg"),
                },
                content_type=MULTIPART_CONTENT,
            )
        self.assertEqual(200, response.status_code, response.content)
        deleted = sorted(call.args[0] for call in delete.call_args_list)
        self.assertEqual(["college_ids/b.jpg", "college_ids/f.jpg"], deleted)

    def test_a_cleared_card_still_loads_the_players_profile(self) -> None:
        # Empty file fields used to fail the response schema: /api/me 500'd and
        # the player looked logged out everywhere.
        self.card(40)
        self.run_command()
        self.client.force_login(self.user)
        response = self.client.get("/api/me")
        self.assertEqual(200, response.status_code, response.content)
        college_id = response.json()["player"]["college_id"]
        self.assertEqual(str(today()), college_id["images_removed_at"])
        self.assertFalse(college_id["card_front"])
