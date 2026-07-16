from typing import Any

from ninja import ModelSchema, Schema

from .models import Form, FormResponse


class FormFieldSchema(Schema):
    key: str
    label: str
    type: str
    required: bool = False
    options: list[str] = []


class FormCreateSchema(Schema):
    title: str
    description: str = ""
    fields: list[FormFieldSchema]
    payment_amount: int | None = None
    is_active: bool = True


class FormListSchema(ModelSchema):
    class Config:
        model = Form
        model_fields = ["id", "title", "description", "slug", "payment_amount", "is_active"]


class FormSchema(ModelSchema):
    class Config:
        model = Form
        model_fields = [
            "id",
            "title",
            "description",
            "slug",
            "fields",
            "payment_amount",
            "is_active",
        ]


class FormResponseCreateSchema(Schema):
    answers: dict[str, Any]


class FormResponseSchema(ModelSchema):
    """Staff view of a response, including the responder's identity."""

    name: str
    email: str
    phone: str

    @staticmethod
    def resolve_name(response: FormResponse) -> str:
        return response.user.get_full_name()

    @staticmethod
    def resolve_email(response: FormResponse) -> str:
        return response.user.email

    @staticmethod
    def resolve_phone(response: FormResponse) -> str:
        return response.user.phone

    class Config:
        model = FormResponse
        model_fields = ["id", "answers", "is_paid", "submitted_at"]


class MyFormResponseSchema(ModelSchema):
    """The current user's own response."""

    class Config:
        model = FormResponse
        model_fields = ["id", "answers", "is_paid", "submitted_at"]


class FormSubmitResponseSchema(Schema):
    status: str
    order: dict[str, Any] | None = None
