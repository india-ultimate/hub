"""Uploaded files on Cloudinary: how names map, and the storage class."""

import json
from typing import Any
from unittest import mock

import cloudinary.exceptions
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.test.client import MULTIPART_CONTENT

from server.storage import kinds
from server.storage.cloudinary import CloudinaryStorage
from server.tests.base import ApiBaseTestCase

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
