"""One template, drawn three ways: the email, the Hub page, the PDF."""

import base64
import functools
import io
from pathlib import Path
from typing import Any, Literal

from django.conf import settings
from django.template.loader import render_to_string

from server.receipts.models import Receipt
from server.receipts.money import format_inr, in_words, india_date

Mode = Literal["email", "page", "pdf"]
# xhtml2pdf and reportlab cost ~69MB and half a second to import, and only the
# PDF needs them. Every gunicorn worker imports this module at startup (there
# is no --preload), so they are imported where they are used, not here.
FONTS = Path(__file__).parent / "fonts"
LOGO = Path(settings.BASE_DIR) / "frontend" / "assets" / "logo-vertical.png"


@functools.cache
def _register_fonts() -> None:
    """xhtml2pdf ignores @font-face paths, so the fonts go to ReportLab directly."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from xhtml2pdf.default import DEFAULT_FONT

    for name, regular, bold in (
        ("IBMPlexSans", "IBMPlexSans-Regular.ttf", "IBMPlexSans-Bold.ttf"),
        ("IBMPlexMono", "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / regular)))
        pdfmetrics.registerFont(TTFont(f"{name}-Bold", str(FONTS / bold)))
        addMapping(name, 0, 0, name)
        addMapping(name, 0, 1, name)
        addMapping(name, 1, 0, f"{name}-Bold")
        addMapping(name, 1, 1, f"{name}-Bold")
        DEFAULT_FONT[name.lower()] = name


@functools.cache
def _logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()


def _context(receipt: Receipt, mode: Mode) -> dict[str, Any]:
    refund = receipt.kind == Receipt.Kind.REFUND
    hub = settings.EMAIL_INVITATION_BASE_URL
    return {
        "mode": mode,
        "doc": receipt,
        "refund": refund,
        "title": "REFUND NOTE" if refund else "RECEIPT",
        "noun": "refund note" if refund else "receipt",
        "issuer": settings.RECEIPT_ISSUER,
        "date": india_date(receipt.issued_at).strftime("%d %b %Y"),
        "original": receipt.original,
        # Only the Hub page links a receipt to its refund notes: the email and
        # the PDF are what was issued at that moment.
        "notes": list(receipt.refund_notes.order_by("issued_at", "id")) if mode == "page" else [],
        "original_date": (
            india_date(receipt.original.issued_at).strftime("%d %b %Y") if receipt.original else ""
        ),
        "rows": [
            {
                **row,
                "index": index,
                "rate_text": format_inr(row["rate"]) if row["rate"] is not None else "",
                "amount_text": format_inr(row["amount"]),
            }
            for index, row in enumerate(receipt.lines, 1)
        ],
        "total_text": format_inr(receipt.total),
        "words": in_words(receipt.total),
        # Email clients block data: images, so the email links the logo.
        "logo": f"{hub}/static/assets/logo-vertical.png" if mode == "email" else _logo_data_uri(),
        "hub_url": f"{hub}/receipts/{receipt.pk}",
    }


def render_html(receipt: Receipt, mode: Mode) -> str:
    return render_to_string("receipts/receipt.html", _context(receipt, mode))


def render_pdf(receipt: Receipt) -> bytes:
    from xhtml2pdf import pisa

    _register_fonts()
    out = io.BytesIO()
    result = pisa.CreatePDF(render_html(receipt, "pdf"), dest=out)
    if result.err:
        raise RuntimeError(f"Could not draw {receipt.number} as a PDF")
    return out.getvalue()
