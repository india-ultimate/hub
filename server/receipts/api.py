"""A person's receipts, and each one as a page or a PDF."""

from typing import Any, cast

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from ninja import Router

from server.core.models import User
from server.receipts.models import Receipt
from server.receipts.money import india_date
from server.receipts.render import render_html, render_pdf
from server.receipts.rows import summary

router = Router()


def _may_see(request: HttpRequest, receipt: Receipt) -> bool:
    user = request.user
    return bool(user.is_staff or receipt.transaction.user_id == user.id)


def _entry(receipt: Receipt) -> dict[str, Any]:
    return {
        "id": receipt.pk,
        "number": receipt.number,
        "kind": receipt.kind,
        "date": india_date(receipt.issued_at).isoformat(),
        # A refund note's first row already says what it refunds.
        "summary": (
            receipt.lines[0]["particulars"]
            if receipt.kind == Receipt.Kind.REFUND and receipt.lines
            else summary(receipt.lines)
        ),
        "total": receipt.total,
        "original_id": receipt.original_id,
    }


@router.get("/receipts", response={200: list[dict[str, Any]]})
def list_receipts(request: HttpRequest) -> list[dict[str, Any]]:
    mine = Receipt.objects.filter(transaction__user=cast(User, request.user))
    notes: dict[int, list[Receipt]] = {}
    for note in mine.filter(kind=Receipt.Kind.REFUND).order_by("issued_at", "id"):
        notes.setdefault(note.original_id or 0, []).append(note)
    listed: list[dict[str, Any]] = []
    for receipt in mine.filter(kind=Receipt.Kind.RECEIPT).order_by("-issued_at", "-id"):
        listed.append(_entry(receipt))
        listed.extend(_entry(note) for note in notes.get(receipt.pk, []))
    return listed


@router.get("/receipts/{receipt_id}/page")
def receipt_page(request: HttpRequest, receipt_id: int) -> HttpResponse:
    receipt = get_object_or_404(
        Receipt.objects.select_related("transaction", "original"), pk=receipt_id
    )
    if not _may_see(request, receipt):
        return HttpResponseForbidden("This receipt is not yours.")
    response = HttpResponse(render_html(receipt, "page"), content_type="text/html")
    # The Hub shows this page in an iframe; Django's default would refuse that.
    response["X-Frame-Options"] = "SAMEORIGIN"
    response["Cache-Control"] = "private, no-store"
    return response


@router.get("/receipts/{receipt_id}/pdf")
def receipt_pdf(request: HttpRequest, receipt_id: int) -> HttpResponse:
    receipt = get_object_or_404(
        Receipt.objects.select_related("transaction", "original"), pk=receipt_id
    )
    if not _may_see(request, receipt):
        return HttpResponseForbidden("This receipt is not yours.")
    response = HttpResponse(render_pdf(receipt), content_type="application/pdf")
    name = receipt.number.replace("/", "-")
    response["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
