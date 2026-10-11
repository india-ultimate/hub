import io
from unittest import mock

import cloudinary.exceptions
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import TestCase
from PIL import Image

from server.core.models import User

UPSTREAM = "server.storage.ckeditor.ckeditor_views.upload"


def png(width: int, height: int, mode: str = "L", image_format: str = "PNG") -> SimpleUploadedFile:
    data = io.BytesIO()
    Image.new(mode, (width, height)).save(data, format=image_format)
    name = f"photo.{image_format.lower()}"
    return SimpleUploadedFile(name, data.getvalue(), content_type=f"image/{image_format.lower()}")


class TestCkeditorUploads(TestCase):
    def setUp(self) -> None:
        staff = User.objects.create(username="staff@x.com", email="staff@x.com", is_staff=True)
        self.client.force_login(staff)

    def upload(self, file: SimpleUploadedFile, query: str = "") -> mock.MagicMock:
        with mock.patch(UPSTREAM, return_value=JsonResponse({"uploaded": "1"})) as upstream:
            self.response = self.client.post(f"/ckeditor/upload/{query}", {"upload": file})
        return upstream

    def test_a_photo_over_50_megapixels_is_refused_in_ckeditors_words(self) -> None:
        # Too big for the server to shrink, so Cloudinary would refuse it.
        upstream = self.upload(png(8000, 7500))
        upstream.assert_not_called()
        self.assertEqual(200, self.response.status_code)
        body = self.response.json()
        self.assertEqual(0, body["uploaded"])
        self.assertIn("under 50 megapixels", body["error"]["message"])

    def test_what_the_server_cant_shrink_is_held_to_cloudinarys_25_mp(self) -> None:
        # Transparent images are shrunk only to ~28 MP, WEBP not at all.
        cases = {
            ("RGBA", "PNG"): "under 28 megapixels",
            ("RGB", "WEBP"): "under 25 megapixels",
        }
        for (mode, image_format), message in cases.items():
            with self.subTest(mode=mode, image_format=image_format):
                self.upload(png(6000, 5000, mode, image_format)).assert_not_called()
                self.assertIn(message, self.response.json()["error"]["message"])

    def test_an_opaque_40_megapixel_photo_goes_through(self) -> None:
        self.upload(png(8000, 5000)).assert_called_once()

    def test_the_upload_dialog_gets_its_message_too(self) -> None:
        self.upload(png(8000, 7500), query="?CKEditorFuncNum=3")
        self.assertContains(self.response, 'callFunction(3, "", "This photo is too large')

    def test_the_dialogs_message_survives_an_apostrophe(self) -> None:
        with mock.patch(UPSTREAM, side_effect=cloudinary.exceptions.Error("too large")):
            response = self.client.post(
                "/ckeditor/upload/?CKEditorFuncNum=3", {"upload": png(20, 20)}
            )
        self.assertContains(response, 'callFunction(3, "", "Couldn\'t save the file. Try again.")')

    def test_a_file_over_10_mb_is_refused(self) -> None:
        big = SimpleUploadedFile("scan.pdf", b"\0" * (10 * 1024 * 1024 + 1))
        self.upload(big).assert_not_called()
        self.assertIn("10 MB or smaller", self.response.json()["error"]["message"])

    def test_cloudinary_refusing_one_is_an_error_message_not_a_500(self) -> None:
        with mock.patch(UPSTREAM, side_effect=cloudinary.exceptions.Error("too large")):
            response = self.client.post("/ckeditor/upload/", {"upload": png(20, 20)})
        self.assertEqual(200, response.status_code)
        self.assertIn("Couldn't save the file", response.json()["error"]["message"])

    def test_an_ordinary_photo_goes_through(self) -> None:
        self.upload(png(1200, 800)).assert_called_once()
        self.assertEqual({"uploaded": "1"}, self.response.json())

    def test_only_staff_can_upload(self) -> None:
        self.client.force_login(User.objects.create(username="p@x.com", email="p@x.com"))
        self.upload(png(20, 20)).assert_not_called()
        self.assertEqual(302, self.response.status_code)
