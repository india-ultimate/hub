"""Uploaded files on Cloudinary: how names map, and the storage class."""

import datetime
import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import cloudinary.exceptions
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.client import MULTIPART_CONTENT

from server.core.models import Accreditation, CollegeId, Player, Team, User, Vaccination
from server.storage import kinds
from server.storage.cloudinary import CloudinaryStorage
from server.tests.base import ApiBaseTestCase
from server.utils import today

CLOUD = "https://res.cloudinary.com/india-ultimate"


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestKinds(SimpleTestCase):
    def test_names_map_to_ids_and_urls(self) -> None:
        cases = {
            "team_logos/a.png": (
                "image",
                "media/team_logos/a",
                f"{CLOUD}/image/upload/media/team_logos/a.png",
            ),
            "accreditation_certificates/c.PDF": (
                "image",
                "media/accreditation_certificates/c",
                f"{CLOUD}/image/upload/media/accreditation_certificates/c.pdf",
            ),
            "team_logos/l.svg": (
                "image",
                "media/team_logos/l",
                f"{CLOUD}/image/upload/media/team_logos/l.svg",
            ),
            "contact-form-attachments/x.docx": (
                "raw",
                "media/contact-form-attachments/x.docx",
                f"{CLOUD}/raw/upload/media/contact-form-attachments/x.docx",
            ),
            "college_ids/noext": (
                "raw",
                "media/college_ids/noext",
                f"{CLOUD}/raw/upload/media/college_ids/noext",
            ),
        }
        for name, (kind, public_id, url) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(kind, kinds.resource_type(name))
                self.assertEqual(public_id, kinds.public_id(name))
                self.assertEqual(url, kinds.url(name))

    def test_only_college_ids_are_resized(self) -> None:
        self.assertIn("transformation", kinds.upload_options("college_ids/a.jpg"))
        self.assertEqual({}, kinds.upload_options("team_logos/a.jpg"))


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestCloudinaryStorage(SimpleTestCase):
    def setUp(self) -> None:
        self.storage = CloudinaryStorage()

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    @mock.patch("cloudinary.uploader.upload")
    def test_save_uploads_under_the_name(self, upload: mock.MagicMock, _: mock.MagicMock) -> None:
        name = self.storage.save("team_logos/a.png", ContentFile(b"png", name="a.png"))
        self.assertEqual("team_logos/a.png", name)
        kwargs = upload.call_args.kwargs
        self.assertEqual("media/team_logos/a", kwargs["public_id"])
        self.assertEqual("image", kwargs["resource_type"])
        self.assertFalse(kwargs["overwrite"])

    @mock.patch("cloudinary.uploader.upload")
    def test_a_taken_name_gets_a_new_one(self, upload: mock.MagicMock) -> None:
        taken = iter([True, False])
        with mock.patch.object(CloudinaryStorage, "exists", side_effect=lambda _: next(taken)):
            name = self.storage.save("team_logos/a.png", ContentFile(b"png", name="a.png"))
        self.assertNotEqual("team_logos/a.png", name)
        self.assertTrue(name.startswith("team_logos/a_") and name.endswith(".png"))

    @mock.patch("cloudinary.uploader.destroy", return_value={"result": "not found"})
    def test_deleting_a_missing_file_is_fine(self, destroy: mock.MagicMock) -> None:
        self.storage.delete("team_logos/gone.png")
        destroy.assert_called_once_with(
            "media/team_logos/gone", resource_type="image", invalidate=True
        )

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    def test_exists_is_false_when_not_found(self, _: mock.MagicMock) -> None:
        self.assertFalse(self.storage.exists("team_logos/a.png"))

    @mock.patch("cloudinary.api.resource", return_value={"bytes": 42})
    def test_size_reads_the_resource(self, _: mock.MagicMock) -> None:
        self.assertEqual(42, self.storage.size("team_logos/a.png"))

    def test_url_of_nothing_is_empty(self) -> None:
        self.assertEqual("", self.storage.url(""))

    @mock.patch("requests.get")
    def test_open_downloads_the_file(self, get: mock.MagicMock) -> None:
        get.return_value = mock.Mock(
            content=b"bytes", status_code=200, raise_for_status=mock.Mock()
        )
        with self.storage.open("ckeditor_uploads/a.png") as f:
            self.assertEqual(b"bytes", f.read())
        get.assert_called_once_with(
            f"{CLOUD}/image/upload/media/ckeditor_uploads/a.png", timeout=30
        )


CLOUDINARY_STORAGES = {
    "default": {"BACKEND": "server.storage.cloudinary.CloudinaryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=CLOUDINARY_STORAGES, CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestUploadsThroughTheApi(ApiBaseTestCase):
    def post_certificate(self) -> Any:
        self.client.force_login(self.user)
        cert = SimpleUploadedFile("cert.pdf", b"%PDF", content_type="application/pdf")
        data = {"date": "2026-01-01", "level": "ADV", "player_id": self.player.id, "wfdf_id": 7}
        return self.client.post(
            "/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": cert},
            content_type=MULTIPART_CONTENT,
        )

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    @mock.patch("cloudinary.uploader.upload")
    def test_an_upload_comes_back_as_a_cloudinary_url(
        self, _u: mock.MagicMock, _r: mock.MagicMock
    ) -> None:
        response = self.post_certificate()
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            f"{CLOUD}/image/upload/media/accreditation_certificates/cert.pdf",
            response.json()["certificate"],
        )

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    @mock.patch("cloudinary.uploader.upload", side_effect=cloudinary.exceptions.Error("down"))
    def test_a_cloudinary_failure_is_a_clear_400(
        self, _u: mock.MagicMock, _r: mock.MagicMock
    ) -> None:
        response = self.post_certificate()
        self.assertEqual(400, response.status_code)
        self.assertEqual("Couldn't save the file. Try again.", response.json()["message"])


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestCopyMedia(TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.settings_override = override_settings(MEDIA_ROOT=self.root)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        user = User.objects.create(username="p@x.com", email="p@x.com")
        self.player = Player.objects.create(user=user, date_of_birth="1995-01-01")
        self.write("team_logos/t.png", b"logo")
        Team.objects.create(name="T", image="team_logos/t.png")
        self.write("team_logos/orphan.png", b"nobody")
        self.write("accreditation_certificates/a.PDF", b"%PDF-1")
        Accreditation.objects.create(
            player=self.player,
            date="2026-01-01",
            level="ADV",
            is_valid=True,
            certificate="accreditation_certificates/a.PDF",
        )
        self.write("vaccination_certificates/v.pdf", b"vax")
        Vaccination.objects.create(
            player=self.player, is_vaccinated=True, certificate="vaccination_certificates/v.pdf"
        )
        self.write("contact-form-attachments/note.docx", b"doc")

    def write(self, name: str, data: bytes) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def run_command(
        self, *args: str, on_cloudinary: dict[str, int] | None = None, head_status: int = 200
    ) -> tuple[str, mock.MagicMock, int]:
        """on_cloudinary: public id -> byte size already stored there."""
        stored = on_cloudinary or {}

        def resource(public_id: str, resource_type: str) -> dict[str, int]:
            if public_id not in stored:
                raise cloudinary.exceptions.NotFound
            return {"bytes": stored[public_id]}

        out = StringIO()
        code = 0
        with mock.patch("cloudinary.uploader.upload") as upload, mock.patch(
            "cloudinary.api.resource", side_effect=resource
        ), mock.patch("requests.head", return_value=mock.Mock(status_code=head_status)):
            try:
                call_command("copy_media_to_cloudinary", *args, stdout=out)
            except SystemExit as e:
                code = int(e.code or 0)
        return out.getvalue(), upload, code

    def uploaded(self, upload: mock.MagicMock) -> list[str]:
        return sorted(c.kwargs["public_id"] for c in upload.call_args_list)

    def test_dry_run_uploads_nothing(self) -> None:
        out, upload, _ = self.run_command("--dry-run")
        upload.assert_not_called()
        self.assertIn("team_logos", out)
        self.assertIn("to copy", out)

    def test_copies_only_what_rows_and_content_point_at(self) -> None:
        _, upload, code = self.run_command()
        self.assertEqual(0, code)
        self.assertEqual(
            [
                "media/accreditation_certificates/a",
                "media/contact-form-attachments/note.docx",
                "media/team_logos/t",
            ],
            self.uploaded(upload),
        )

    def test_a_second_run_skips_what_is_already_there(self) -> None:
        # Same id and byte size already on Cloudinary: skipped, even if the
        # name's extension is upper case.
        _, upload, _ = self.run_command(on_cloudinary={"media/team_logos/t": len(b"logo")})
        self.assertNotIn("media/team_logos/t", self.uploaded(upload))

    def test_expired_college_ids_are_left_out(self) -> None:
        self.write("college_ids/old_f.jpg", b"f")
        self.write("college_ids/old_b.jpg", b"b")
        CollegeId.objects.create(
            player=self.player,
            expiry=today() - datetime.timedelta(days=31),
            card_front="college_ids/old_f.jpg",
            card_back="college_ids/old_b.jpg",
        )
        _, upload, _ = self.run_command()
        self.assertFalse(any("college_ids" in i for i in self.uploaded(upload)))

    def test_missing_files_are_listed(self) -> None:
        Accreditation.objects.create(
            player=Player.objects.create(
                user=User.objects.create(username="q@x.com", email="q@x.com"),
                date_of_birth="1995-01-01",
            ),
            date="2026-01-01",
            level="STD",
            is_valid=True,
            certificate="accreditation_certificates/missing.pdf",
        )
        out, _, _ = self.run_command()
        self.assertIn("Missing on disk", out)
        self.assertIn("accreditation_certificates/missing.pdf", out)

    def test_a_file_that_wont_serve_counts_as_failed(self) -> None:
        out, _, code = self.run_command(head_status=401)
        self.assertEqual(1, code)
        self.assertIn("failed", out)


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestOldMediaLinks(TestCase):
    def test_an_old_link_goes_to_cloudinary(self) -> None:
        response = Client().get("/media/accreditation_certificates/a.PDF")
        self.assertEqual(301, response.status_code)
        self.assertEqual(
            f"{CLOUD}/image/upload/media/accreditation_certificates/a.pdf", response["Location"]
        )

    def test_a_raw_file_keeps_its_name(self) -> None:
        response = Client().get("/media/contact-form-attachments/x.docx")
        self.assertEqual(
            f"{CLOUD}/raw/upload/media/contact-form-attachments/x.docx", response["Location"]
        )

    def test_archived_and_odd_paths_are_404(self) -> None:
        for path in ("/media/vaccination_certificates/v.pdf", "/media/../etc/passwd"):
            with self.subTest(path=path):
                self.assertEqual(404, Client().get(path).status_code)
