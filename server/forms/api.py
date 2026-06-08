from typing import Any

from django.db.models import QuerySet
from ninja import Router

from server.schema import Response
from server.transaction.models import AuthenticatedHttpRequest
from server.types import message_response
from server.utils import slugify_max

from .models import Form, FormResponse
from .schema import (
    FormCreateSchema,
    FormListSchema,
    FormResponseCreateSchema,
    FormResponseSchema,
    FormSchema,
    FormSubmitResponseSchema,
    MyFormResponseSchema,
)
from .utils import create_form_payment_order, send_form_submission_email, validate_answers

router = Router()


def _unique_slug(title: str) -> str:
    base = slugify_max(title) or "form"
    slug = base
    n = 1
    while Form.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


@router.get("/", response={200: list[FormListSchema]})
def list_forms(request: AuthenticatedHttpRequest) -> QuerySet[Form]:
    forms = Form.objects.all() if request.user.is_staff else Form.objects.filter(is_active=True)
    return forms.order_by("-created_at")


@router.post("/", response={200: FormSchema, 400: Response, 401: Response})
def create_form(
    request: AuthenticatedHttpRequest, data: FormCreateSchema
) -> tuple[int, Form | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can create forms"}

    form = Form.objects.create(
        title=data.title,
        description=data.description,
        slug=_unique_slug(data.title),
        fields=[f.dict() for f in data.fields],
        payment_amount=data.payment_amount,
        created_by=request.user,
    )
    return 200, form


@router.get("/{slug}", response={200: FormSchema, 404: Response})
def get_form(request: AuthenticatedHttpRequest, slug: str) -> tuple[int, Form | message_response]:
    try:
        return 200, Form.objects.get(slug=slug)
    except Form.DoesNotExist:
        return 404, {"message": "Form does not exist"}


@router.put("/{slug}", response={200: FormSchema, 401: Response, 404: Response})
def update_form(
    request: AuthenticatedHttpRequest, slug: str, data: FormCreateSchema
) -> tuple[int, Form | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can edit forms"}

    try:
        form = Form.objects.get(slug=slug)
    except Form.DoesNotExist:
        return 404, {"message": "Form does not exist"}

    form.title = data.title
    form.description = data.description
    form.fields = [f.dict() for f in data.fields]
    form.payment_amount = data.payment_amount
    form.save(update_fields=["title", "description", "fields", "payment_amount"])
    return 200, form


@router.post(
    "/{slug}/responses",
    response={200: FormSubmitResponseSchema, 400: Response, 404: Response, 502: str},
)
def submit_response(
    request: AuthenticatedHttpRequest, slug: str, data: FormResponseCreateSchema
) -> tuple[int, dict[str, Any] | message_response | str]:
    try:
        form = Form.objects.get(slug=slug, is_active=True)
    except Form.DoesNotExist:
        return 404, {"message": "Form does not exist or is not active"}

    error = validate_answers(form, data.answers)
    if error:
        return 400, {"message": error}

    response = FormResponse.objects.create(form=form, user=request.user, answers=data.answers)

    if form.needs_payment:
        order = create_form_payment_order(request, form, response)
        if order is None:
            return 502, "Failed to connect to Razorpay."
        return 200, {"status": "payment_required", "order": order}

    response.is_paid = True
    response.save(update_fields=["is_paid"])
    send_form_submission_email(response)
    return 200, {"status": "ok"}


@router.get(
    "/{slug}/responses", response={200: list[FormResponseSchema], 401: Response, 404: Response}
)
def list_responses(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QuerySet[FormResponse] | message_response]:
    if not request.user.is_staff:
        return 401, {"message": "Only Admins can view responses"}

    try:
        form = Form.objects.get(slug=slug)
    except Form.DoesNotExist:
        return 404, {"message": "Form does not exist"}

    # Only finalized submissions count. Unpaid rows on paid forms are transient
    # payment-tracking state (free-form responses are marked paid on submit).
    return (
        200,
        form.responses.filter(is_paid=True).select_related("user").order_by("-submitted_at"),
    )


@router.get("/{slug}/my-responses", response={200: list[MyFormResponseSchema], 404: Response})
def list_my_responses(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QuerySet[FormResponse] | message_response]:
    try:
        form = Form.objects.get(slug=slug)
    except Form.DoesNotExist:
        return 404, {"message": "Form does not exist"}

    return (
        200,
        form.responses.filter(user=request.user, is_paid=True).order_by("-submitted_at"),
    )
