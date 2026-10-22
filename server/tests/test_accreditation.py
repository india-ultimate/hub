import datetime
import io
import json
from io import StringIO
from typing import Any
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.test.client import MULTIPART_CONTENT
from django.utils.timezone import now
from pypdf import PdfReader, PdfWriter

from server.accreditation.models import Accreditation
from server.core.models import Guardianship, Player, User
from server.tests.base import ApiBaseTestCase, wfdf_certificate_pdf
from server.tests.test_subscription_model import make_player
from server.utils import today


class TestAccreditation(ApiBaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.user)

    def upload(self, pdf: bytes | None = None, player_id: int | None = None) -> Any:
        certificate = SimpleUploadedFile(
            "certificate.pdf", pdf or wfdf_certificate_pdf(), content_type="application/pdf"
        )
        return self.client.post(
            path="/api/accreditation",
            data={
                "accreditation": json.dumps({"player_id": player_id or self.player.id}),
                "certificate": certificate,
            },
            content_type=MULTIPART_CONTENT,
        )

    def test_the_details_are_read_from_the_certificate(self) -> None:
        issued = datetime.date(2026, 10, 1)
        response = self.upload(
            wfdf_certificate_pdf(issued=issued, expires=datetime.date(2028, 3, 31))
        )
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual("5905130059NR", data["certificate_code"])
        self.assertEqual("ADV", data["level"])
        self.assertEqual("2026-10-01", data["date"])
        self.assertEqual("2028-03-31", data["expiry_date"])
        self.assertTrue(data["is_valid"])
        self.assertTrue(len(data["certificate"]) > 0)
        self.assertEqual(self.player.id, data["player"])

    def test_a_standard_certificate(self) -> None:
        response = self.upload(wfdf_certificate_pdf(level="Standard"))
        self.assertEqual("STD", response.json()["level"])

    def test_an_expired_certificate_is_saved_as_not_valid(self) -> None:
        issued = now().date() - datetime.timedelta(days=600)
        pdf = wfdf_certificate_pdf(issued=issued, expires=now().date() - datetime.timedelta(days=1))
        response = self.upload(pdf)
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()["is_valid"])

    def test_a_certificate_expiring_today_is_valid(self) -> None:
        issued = now().date() - datetime.timedelta(days=545)
        response = self.upload(wfdf_certificate_pdf(issued=issued, expires=today()))
        self.assertTrue(response.json()["is_valid"])

    def test_a_certificate_issued_in_the_future_is_refused(self) -> None:
        issued = today() + datetime.timedelta(days=2)
        response = self.upload(wfdf_certificate_pdf(issued=issued))
        self.assertEqual(400, response.status_code)
        self.assertIn("future", response.json()["message"])
        self.assertFalse(Accreditation.objects.exists())

    def test_a_certificate_issued_tomorrow_east_of_india_is_accepted(self) -> None:
        issued = today() + datetime.timedelta(days=1)
        self.assertEqual(200, self.upload(wfdf_certificate_pdf(issued=issued)).status_code)

    def test_an_expiry_glued_to_its_label_is_read(self) -> None:
        expires = datetime.date(2028, 2, 2)
        response = self.upload(wfdf_certificate_pdf(expires=expires, glued=True))
        self.assertEqual("2028-02-02", response.json()["expiry_date"])

    def test_a_certificate_has_one_page(self) -> None:
        writer = PdfWriter()
        for _ in range(2):
            writer.append(PdfReader(io.BytesIO(wfdf_certificate_pdf())))
        pdf = io.BytesIO()
        writer.write(pdf)
        self.assertEqual(400, self.upload(pdf.getvalue()).status_code)

    def test_a_date_that_does_not_exist_is_refused(self) -> None:
        pdf = wfdf_certificate_pdf().replace(b"Rahul Sharma", b"31 June 2026")
        self.assertEqual(400, self.upload(pdf).status_code)

    def test_a_pdf_that_is_not_a_wfdf_academy_certificate_is_refused(self) -> None:
        for pdf in [
            wfdf_certificate_pdf(code="12345"),
            wfdf_certificate_pdf(level="Gold"),
            b"%PDF-1.7 not really",
            b"\x89PNG\r\n",
        ]:
            response = self.upload(pdf)
            self.assertEqual(400, response.status_code)
            self.assertIn("WFDF Academy", response.json()["message"])
        self.assertFalse(Accreditation.objects.exists())

    def test_a_new_certificate_replaces_the_old_and_keeps_the_wfdf_id(self) -> None:
        self.assertEqual(200, self.upload().status_code)
        Accreditation.objects.filter(player=self.player).update(wfdf_id=777)
        self.assertEqual(
            200,
            self.upload(wfdf_certificate_pdf(code="1111111111AB", level="Standard")).status_code,
        )
        accreditation = Accreditation.objects.get(player=self.player)
        self.assertEqual(777, accreditation.wfdf_id)
        self.assertEqual("1111111111AB", accreditation.certificate_code)
        self.assertEqual("STD", accreditation.level)

    def test_accreditation_duplicate(self) -> None:
        self.assertEqual(200, self.upload().status_code)

        username = email = "foo@example.com"

        user = User.objects.create(username=username, email=email)
        player = Player.objects.create(date_of_birth="2000-01-01", user=user)
        Guardianship.objects.create(relation="LG", user=self.user, player=player)
        response = self.upload(player_id=player.id)
        self.assertEqual(400, response.status_code)
        self.assertIn("already on another player's profile", response.json()["message"])

    def test_without_an_expiry_it_lasts_18_months(self) -> None:
        accreditation = Accreditation.objects.create(
            player=self.player, level="STD", date=datetime.date(2026, 1, 31), certificate="c.pdf"
        )
        self.assertEqual(datetime.date(2027, 7, 31), accreditation.expiry_date)


class TestInvalidateAccreditations(TestCase):
    def test_validity_follows_the_expiry_date(self) -> None:
        issued = now().date() - datetime.timedelta(days=100)
        expiries = {
            "expired@example.com": now().date() - datetime.timedelta(days=1),
            "today@example.com": now().date(),
            "later@example.com": now().date() + datetime.timedelta(days=1),
        }
        for email, expiry in expiries.items():
            Accreditation.objects.create(
                player=make_player(email),
                level="ADV",
                date=issued,
                expiry_date=expiry,
                certificate="c.pdf",
            )
        Accreditation.objects.update(is_valid=True)
        Accreditation.objects.filter(player__user__email="later@example.com").update(is_valid=False)

        with mock.patch("server.management.commands.invalidate_accreditations.today") as today:
            today.return_value = now().date()
            call_command("invalidate_accreditations", stdout=StringIO())

        valid = dict(Accreditation.objects.values_list("player__user__email", "is_valid"))
        self.assertEqual(
            {"expired@example.com": False, "today@example.com": True, "later@example.com": True},
            valid,
        )
