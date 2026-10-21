"""Uploaded files on Cloudinary: how names map, and the storage class."""

import importlib.util
import io
import json
import os
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any
from unittest import mock

import cloudinary.exceptions
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.test.client import MULTIPART_CONTENT
from PIL import Image

from server.storage import kinds, shrink
from server.storage.cloudinary import CloudinaryStorage
from server.tests.base import ApiBaseTestCase, wfdf_certificate_pdf

CLOUD = "https://res.cloudinary.com/india-ultimate"


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestKinds(SimpleTestCase):
    def test_names_map_to_ids_and_urls(self) -> None:
        cases = {
            "team_logos/a.png": (
                "image",
                "media/team_logos/a_png",
                f"{CLOUD}/image/upload/media/team_logos/a_png.png",
            ),
            "accreditation_certificates/c.PDF": (
                "image",
                "media/accreditation_certificates/c_PDF",
                f"{CLOUD}/image/upload/media/accreditation_certificates/c_PDF.pdf",
            ),
            "team_logos/l.svg": (
                "image",
                "media/team_logos/l_svg",
                f"{CLOUD}/image/upload/media/team_logos/l_svg.svg",
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

    def test_urls_are_percent_encoded(self) -> None:
        # Old contact attachments have spaces; '#' would cut an emailed link.
        self.assertEqual(
            f"{CLOUD}/raw/upload/media/contact-form-attachments/a%20b%23c.docx",
            kinds.url("contact-form-attachments/a b#c.docx"),
        )

    def test_names_differing_only_by_extension_get_their_own_files(self) -> None:
        # 16 such pairs in production, e.g. back.jpeg and back.jpg, x.pdf and x.PDF.
        pairs = [("college_ids/back.jpeg", "college_ids/back.jpg"), ("a/x.pdf", "a/x.PDF")]
        for one, other in pairs:
            with self.subTest(one=one):
                self.assertNotEqual(kinds.public_id(one), kinds.public_id(other))
                self.assertNotEqual(kinds.url(one), kinds.url(other))

    @override_settings(CLOUDINARY_MEDIA_PREFIX="staging/media/")
    def test_staging_files_live_apart_from_productions(self) -> None:
        # Same cloud: a staging delete must never reach a production file.
        self.assertEqual("staging/media/college_ids/a_jpg", kinds.public_id("college_ids/a.jpg"))
        self.assertEqual(
            f"{CLOUD}/raw/upload/staging/media/contact-form-attachments/x.docx",
            kinds.url("contact-form-attachments/x.docx"),
        )

    def test_a_college_id_that_isnt_an_image_isnt_resized(self) -> None:
        # Cloudinary refuses a transformation on a raw file.
        self.assertEqual({}, kinds.upload_options("college_ids/card.jfif"))

    def test_images_are_kept_in_their_names_format(self) -> None:
        # Cloudinary keeps an image in its real format: a "Certificate.pdf"
        # that's a PNG would answer 401 at .pdf. Converted on upload, it can't.
        cases = {"a.PDF": "pdf", "a.jpeg": "jpg", "a.JPG": "jpg", "a.png": "png", "a.docx": None}
        for name, stored in cases.items():
            with self.subTest(name=name):
                self.assertEqual(stored, kinds.stored_format(f"team_logos/{name}"))

    def test_only_college_ids_are_resized(self) -> None:
        self.assertIn("transformation", kinds.upload_options("college_ids/a.jpg"))
        self.assertEqual({}, kinds.upload_options("team_logos/a.jpg"))


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestCloudinaryStorage(SimpleTestCase):
    def setUp(self) -> None:
        self.storage = CloudinaryStorage()

    @mock.patch("cloudinary.api.resource")
    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_save_uploads_under_the_name(
        self, upload: mock.MagicMock, resource: mock.MagicMock
    ) -> None:
        name = self.storage.save("team_logos/a.png", ContentFile(b"png", name="a.png"))
        self.assertEqual("team_logos/a.png", name)
        kwargs = upload.call_args.kwargs
        self.assertEqual("media/team_logos/a_png", kwargs["public_id"])
        self.assertEqual("image", kwargs["resource_type"])
        self.assertEqual("png", kwargs["format"])
        self.assertFalse(kwargs["overwrite"])
        # No Admin API call on upload: it's rate-limited (500 an hour on free).
        resource.assert_not_called()

    @mock.patch("cloudinary.uploader.upload")
    def test_a_taken_name_gets_a_new_one(self, upload: mock.MagicMock) -> None:
        # overwrite=False: Cloudinary answers "existing" instead of replacing.
        upload.side_effect = [{"existing": True}, {"existing": False}]
        name = self.storage.save("team_logos/a.png", ContentFile(b"png", name="a.png"))
        self.assertNotEqual("team_logos/a.png", name)
        self.assertTrue(name.startswith("team_logos/a_") and name.endswith(".png"))
        self.assertEqual(2, upload.call_count)

    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_unsafe_names_are_cleaned(self, upload: mock.MagicMock) -> None:
        # The contact form saves the attachment's own name; Cloudinary refuses
        # ids with ? & # % and the like.
        name = self.storage.save(
            "contact-form-attachments/Invoice #3 & co?.pdf", ContentFile(b"%PDF", name="x")
        )
        self.assertEqual("contact-form-attachments/Invoice_3__co.pdf", name)
        self.assertEqual(
            "media/contact-form-attachments/Invoice_3__co_pdf",
            upload.call_args.kwargs["public_id"],
        )

    @mock.patch("cloudinary.uploader.destroy", return_value={"result": "not found"})
    def test_deleting_a_missing_file_is_fine(self, destroy: mock.MagicMock) -> None:
        self.storage.delete("team_logos/gone.png")
        destroy.assert_called_once_with(
            "media/team_logos/gone_png", resource_type="image", invalidate=True
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
            f"{CLOUD}/image/upload/media/ckeditor_uploads/a_png.png", timeout=30
        )


def png(width: int, height: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "red").save(out, format="PNG")
    return out.getvalue()


@mock.patch.object(shrink, "MAX_PIXELS", 100)
class TestShrink(SimpleTestCase):
    # The free plan refuses images over 25 megapixels or 10 MB: 12 on the
    # disk are, among them team logos of 8334 x 8334.
    def test_an_image_over_the_limit_is_shrunk(self) -> None:
        small = shrink.shrunk(io.BytesIO(png(20, 20)))
        if small is None:
            self.fail("not shrunk")
        with Image.open(small) as image:
            self.assertEqual("PNG", image.format)
            self.assertLessEqual(image.width * image.height, 100)

    def test_an_image_within_the_limit_or_not_an_image_is_left(self) -> None:
        self.assertIsNone(shrink.shrunk(io.BytesIO(png(5, 5))))
        self.assertIsNone(shrink.shrunk(io.BytesIO(b"%PDF-1.4")))

    def test_a_compressed_tiff_is_shrunk(self) -> None:
        # The JPEG quality option is passed only to JPEG and WebP: a TIFF
        # with it raised "quality setting only supported for 'jpeg'".
        tiff = io.BytesIO()
        Image.new("RGB", (20, 20)).save(tiff, format="TIFF", compression="tiff_lzw")
        self.assertIsNotNone(shrink.shrunk(tiff))

    def test_what_pillow_cant_save_is_left_as_it_is(self) -> None:
        # The upload goes ahead with the original, as before shrinking.
        f = io.BytesIO(png(20, 20))
        with mock.patch("PIL.Image.Image.save", side_effect=KeyError("PSD")):
            self.assertIsNone(shrink.shrunk(f))
        self.assertEqual(0, f.tell())

    def test_an_animated_gif_is_left_as_it_is(self) -> None:
        # Shrinking would keep only the first frame.
        gif = io.BytesIO()
        frames = [Image.new("RGB", (20, 20), c) for c in ("red", "blue")]
        frames[0].save(gif, format="GIF", save_all=True, append_images=frames[1:])
        self.assertIsNone(shrink.shrunk(gif))

    def test_one_too_large_to_decode_is_left_as_it_is(self) -> None:
        # A tiny file can claim huge dimensions: decoding it would take GBs.
        with mock.patch.object(shrink, "MAX_PEAK_BYTES", shrink.peak_bytes("RGB", 20 * 20) - 1):
            self.assertIsNone(shrink.shrunk(io.BytesIO(png(20, 20))))

    def test_the_largest_shrink_fits_an_app_machine(self) -> None:
        # No swap: a shrink that doesn't fit beside ~500 MB of workers kills one.
        with (Path(__file__).parents[2] / "fly.toml").open("rb") as f:
            (app,) = (vm for vm in tomllib.load(f)["vm"] if vm["processes"] == ["app"])
        memory = app["memory"].lower()
        mib = (
            int(memory.removesuffix("gb")) * 1024
            if memory.endswith("gb")
            else int(memory.removesuffix("mb"))
        )
        self.assertLessEqual(shrink.MAX_PEAK_BYTES + 500_000_000, mib * 1024 * 1024 * 0.9)

    def test_what_is_shrunk_is_counted_as_pillow_holds_it(self) -> None:
        # Measured peaks: a 145 KB LA PNG (75 MP) took 809 MB, an F TIFF 642 MB.
        fits = shrink.MAX_PEAK_BYTES
        cases = {
            ("RGB", 50_000_000): True,  # a 50 MP phone photo: college IDs
            ("L", 100_000_000): True,
            ("RGBA", 37_500_000): False,  # copied premultiplied before resizing
            ("RGBA", 32_500_000): False,  # measured 472 MB: 3.6x what it decodes to
            ("LA", 29_700_000): False,  # measured 445 MB: too close for Linux
            ("RGBA", 28_000_000): True,
            ("LA", 75_000_000): False,  # 4 bytes a pixel, not 2
            ("P", 150_000_000): True,  # resized a byte a pixel: measured 183 MB
            ("F", 144_000_000): False,  # 4 bytes a pixel, not 1
            ("I;16", 150_000_000): False,
        }
        for (mode, pixels), shrinkable in cases.items():
            with self.subTest(mode=mode, pixels=pixels):
                self.assertEqual(shrinkable, shrink.peak_bytes(mode, pixels) <= fits)

    def test_a_webp_is_never_decoded(self) -> None:
        # Pillow's WEBP decoder needs ~1 GB for one over 25 MP, whatever its mode.
        webp = io.BytesIO()
        Image.new("RGB", (20, 20)).save(webp, format="WEBP")
        with mock.patch.object(shrink, "MAX_PIXELS", 100):
            self.assertIsNone(shrink.shrunk(webp))

    def test_16_bit_grey_is_left_without_decoding(self) -> None:
        # Pillow can't resize I;16: decoding it would only waste memory.
        grey = io.BytesIO()
        Image.new("I;16", (20, 20)).save(grey, format="PNG")
        with mock.patch.object(shrink, "MAX_PIXELS", 100), self.assertNoLogs(shrink.logger):
            self.assertIsNone(shrink.shrunk(grey))

    def test_a_phone_photo_stays_upright(self) -> None:
        photo = io.BytesIO()
        exif = Image.Exif()
        exif[0x0112] = 6  # orientation: rotate 90 degrees
        Image.new("RGB", (20, 10)).save(photo, format="JPEG", exif=exif)
        small = shrink.shrunk(photo)
        if small is None:
            self.fail("not shrunk")
        with Image.open(small) as image:
            self.assertGreater(image.height, image.width)

    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_a_raw_file_is_never_shrunk(self, upload: mock.MagicMock) -> None:
        # .tif is stored raw, with no pixel limit: a big scan uploads as it is.
        data = png(20, 20)
        CloudinaryStorage().save("contact-form-attachments/scan.tif", ContentFile(data, name="x"))
        self.assertEqual(data, upload.call_args.args[0].read())

    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_the_storage_uploads_the_shrunk_image(self, upload: mock.MagicMock) -> None:
        CloudinaryStorage().save("team_logos/big.png", ContentFile(png(20, 20), name="big.png"))
        with Image.open(upload.call_args.args[0]) as image:
            self.assertLessEqual(image.width * image.height, 100)


CLOUDINARY_STORAGES = {
    "default": {"BACKEND": "server.storage.cloudinary.CloudinaryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=CLOUDINARY_STORAGES, CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestUploadsThroughTheApi(ApiBaseTestCase):
    def post_certificate(self) -> Any:
        self.client.force_login(self.user)
        cert = SimpleUploadedFile(
            "cert.pdf", wfdf_certificate_pdf(), content_type="application/pdf"
        )
        data = {"player_id": self.player.id}
        return self.client.post(
            "/api/accreditation",
            data={"accreditation": json.dumps(data), "certificate": cert},
            content_type=MULTIPART_CONTENT,
        )

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_an_upload_comes_back_as_a_cloudinary_url(
        self, _u: mock.MagicMock, _r: mock.MagicMock
    ) -> None:
        response = self.post_certificate()
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            f"{CLOUD}/image/upload/media/accreditation_certificates/cert_pdf.pdf",
            response.json()["certificate"],
        )

    @mock.patch("cloudinary.uploader.upload", return_value={"existing": False})
    def test_a_contact_attachment_link_points_at_cloudinary(self, _: mock.MagicMock) -> None:
        # Built from the storage's URL, not MEDIA_URL, which nothing serves.
        self.client.force_login(self.user)
        form = json.dumps({"subject": "Help", "description": "See attached"})
        attachment = SimpleUploadedFile("note.pdf", b"%PDF", content_type="application/pdf")
        response = self.client.post(
            "/api/contact",
            data={"contact_form": form, "attachment": attachment},
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn(
            f"{CLOUD}/image/upload/media/contact-form-attachments/note_pdf.pdf",
            mail.outbox[0].body,
        )

    @mock.patch("cloudinary.api.resource", side_effect=cloudinary.exceptions.NotFound)
    @mock.patch("cloudinary.uploader.upload", side_effect=cloudinary.exceptions.Error("down"))
    def test_a_cloudinary_failure_is_a_clear_400(
        self, _u: mock.MagicMock, _r: mock.MagicMock
    ) -> None:
        with self.assertLogs("server.api", "ERROR"):  # so Sentry sees it
            response = self.post_certificate()
        self.assertEqual(400, response.status_code)
        self.assertEqual("Couldn't save the file. Try again.", response.json()["message"])


class TestCronEnv(SimpleTestCase):
    def test_the_nightly_jobs_get_the_cloudinary_secret(self) -> None:
        # Without it, remove_expired_college_ids can't delete the Cloudinary copies.
        spec = importlib.util.spec_from_file_location(
            "make_cron_env", Path(__file__).parents[2] / "deploy/make_cron_env.py"
        )
        if spec is None or spec.loader is None:
            self.fail("deploy/make_cron_env.py not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        env = {
            "CLOUDINARY_API_SECRET": "s3cret",
            "CLOUDINARY_MEDIA_PREFIX": "staging/media/",
            "FLY_APP_NAME": "upai-hub",
        }
        with mock.patch.object(module, "ROOT", root), mock.patch.dict("os.environ", env):
            os.environ.pop("TOPSCORE_PASSWORD", None)
            module.main()
        written = (root / "cron/env").read_text()
        self.assertIn("export CLOUDINARY_API_SECRET=s3cret", written)
        # Or staging's nightly deletes would reach production's files.
        self.assertIn("export CLOUDINARY_MEDIA_PREFIX=staging/media/", written)
        # Or cron would run on SQLite, not refuse, when DATABASE_URL is missing.
        self.assertIn("export FLY_APP_NAME=upai-hub", written)
        # Unset stays unset: an exported "None" would become the id prefix.
        self.assertNotIn("TOPSCORE_PASSWORD", written)


@override_settings(CLOUDINARY_CLOUD_NAME="india-ultimate")
class TestOldMediaLinks(TestCase):
    def test_an_old_link_goes_to_cloudinary(self) -> None:
        response = Client().get("/media/accreditation_certificates/a.PDF")
        self.assertEqual(301, response.status_code)
        self.assertEqual(
            f"{CLOUD}/image/upload/media/accreditation_certificates/a_PDF.pdf",
            response["Location"],
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
