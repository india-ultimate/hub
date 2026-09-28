import datetime
import io
import os
import subprocess
import sys
from typing import Any, cast

from django.test import SimpleTestCase, TestCase
from pypdf import PdfReader

from server.receipts.models import Receipt
from server.receipts.render import Mode, render_html, render_pdf
from server.transaction.models import RazorpayTransaction

from .test_subscription_model import make_player

UTC = datetime.timezone.utc


class RenderTestCase(TestCase):
    def setUp(self) -> None:
        user = make_player("render@example.com").user
        self.transaction = RazorpayTransaction.objects.create(
            order_id="order_R", payment_id="pay_R", amount=225000, currency="INR", user=user
        )
        self.receipt = Receipt.objects.create(
            kind=Receipt.Kind.RECEIPT,
            transaction=self.transaction,
            number="IU/2026-27/00148",
            financial_year="2026-27",
            sequence=148,
            issued_at=datetime.datetime(2026, 9, 14, 6, 0, tzinfo=UTC),
            payer_name="Priya Rao",
            payer_email="priya@example.com",
            payer_phone="+919845012345",
            lines=[
                {
                    "particulars": "Regular Subscription, Season 2026-2027",
                    "people": ["Asha Rao (IU-26-0042)", "Meera Rao (IU-26-0043)"],
                    "quantity": 2,
                    "rate": 75000,
                    "amount": 150000,
                },
                {
                    "particulars": "Upgrade from Regular to Patron Subscription, Season 2026-2027",
                    "people": ["Arjun Rao (IU-24-0311)"],
                    "quantity": 1,
                    "rate": 75000,
                    "amount": 75000,
                },
            ],
            total=225000,
            reference="pay_R",
            order_id="order_R",
        )


class TestHtml(RenderTestCase):
    def test_every_mode_prints_the_receipt(self) -> None:
        modes: tuple[Mode, ...] = ("email", "page", "pdf")
        for mode in modes:
            html = render_html(self.receipt, mode)
            for text in (
                "RECEIPT",
                "IU/2026-27/00148",
                "14 Sep 2026",
                "Received from",
                "Priya Rao",
                "Meera Rao (IU-26-0043)",
                "1,500.00",
                "2,250.00",
                "Rupees Two Thousand Two Hundred Fifty Only",
                "pay_R",
                "33AAECF4262G1ZW",
                "does not require a signature",
            ):
                self.assertIn(text, html, f"{mode}: {text}")
            self.assertNotIn("DONATED", html.upper())

    def test_the_email_links_to_the_hub(self) -> None:
        self.assertIn(f"/receipts/{self.receipt.pk}", render_html(self.receipt, "email"))

    def test_the_phone_only_quantity_line_is_hidden_inline_and_shown_by_the_media_query(
        self,
    ) -> None:
        # Clients that strip <style> must not show "2 x 750.00" twice.
        for mode in ("email", "page"):
            html = render_html(self.receipt, mode)  # type: ignore[arg-type]
            self.assertIn('class="mult mono" style="display:none;', html)
            self.assertIn(".mult { display: block !important; }", html)

    def test_a_legacy_row_without_a_rate_has_no_quantity_line(self) -> None:
        self.receipt.lines = [
            {
                "particulars": "Subscription, Season 2025-2026",
                "people": ["A", "B", "C"],
                "quantity": 3,
                "rate": None,
                "amount": 200000,
            }
        ]
        for mode in ("email", "page", "pdf"):
            self.assertNotIn('class="mult', render_html(self.receipt, mode))  # type: ignore[arg-type]

    def test_a_refund_note_names_its_receipt(self) -> None:
        note = Receipt.objects.create(
            kind=Receipt.Kind.REFUND,
            transaction=self.transaction,
            original=self.receipt,
            number="RF/2026-27/00007",
            financial_year="2026-27",
            sequence=7,
            issued_at=datetime.datetime(2026, 10, 2, 6, 0, tzinfo=UTC),
            payer_name="Priya Rao",
            lines=[
                {
                    "particulars": "Refund: Regular Subscription, Season 2026-2027",
                    "people": [],
                    "quantity": 1,
                    "rate": 75000,
                    "amount": 75000,
                }
            ],
            total=75000,
            reference="rfnd_R",
            order_id="order_R",
        )
        html = render_html(note, "page")
        for text in (
            "REFUND NOTE",
            "Refunded to",
            "Against receipt",
            "IU/2026-27/00148",
            "rfnd_R",
            "Rupees Seven Hundred Fifty Only",
        ):
            self.assertIn(text, html)
        self.assertIn(f'href="/receipts/{self.receipt.pk}"', html)
        # The receipt's Hub page lists the note; its email and PDF do not.
        self.assertIn('href="/receipts/%d"' % note.pk, render_html(self.receipt, "page"))
        self.assertNotIn("RF/2026-27/00007", render_html(self.receipt, "email"))


class TestPdf(RenderTestCase):
    def test_it_is_one_a4_page_with_the_text_and_the_fonts(self) -> None:
        reader = PdfReader(io.BytesIO(render_pdf(self.receipt)))
        self.assertEqual(len(reader.pages), 1)
        box = reader.pages[0].mediabox
        self.assertEqual((round(float(box.width)), round(float(box.height))), (595, 842))  # A4
        text = reader.pages[0].extract_text()
        for expected in ("IU/2026-27/00148", "2,250.00", "Two Thousand Two Hundred Fifty"):
            self.assertIn(expected, text)
        self.assertNotIn("2 \u00d7 750.00", text)  # the phone-only line stays hidden
        resources = cast(dict[str, Any], reader.pages[0]["/Resources"])
        fonts = {str(font.get_object()["/BaseFont"]) for font in resources["/Font"].values()}
        self.assertTrue(any("IBMPlexSans" in f for f in fonts), fonts)
        self.assertTrue(any("IBMPlexMono" in f for f in fonts), fonts)


class TestImportCost(SimpleTestCase):
    def test_importing_the_renderer_leaves_xhtml2pdf_alone(self) -> None:
        """Every gunicorn worker imports this module; only the PDF path pays
        the ~69MB xhtml2pdf and reportlab cost, and it pays it on first use."""
        script = (
            "import sys, django; django.setup(); import server.receipts.render; "
            "sys.exit(1 if 'xhtml2pdf' in sys.modules else 0)"
        )
        answer = subprocess.run(
            [sys.executable, "-c", script],  # noqa: S603
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "hub.test_settings"},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(answer.returncode, 0, answer.stderr)
