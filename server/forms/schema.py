from typing import Any

from ninja import ModelSchema, Schema

from .models import Form, FormResponse


class FormFieldSchema(Schema):
    key: str
    label: str
    type: str
    required: bool = False
    options: list[str] = []
    section: str = ""
    goto: dict[str, str] = {}


class FormSectionSchema(Schema):
    key: str
    title: str = ""
    description: str = ""
    next: str = ""


class FormCreateSchema(Schema):
    title: str
    description: str = ""
    sections: list[FormSectionSchema] = []
    fields: list[FormFieldSchema]
    payment_amount: int | None = None
    is_active: bool = True


class FormListSchema(ModelSchema):
    class Meta:
        model = Form
        fields = ["id", "title", "description", "slug", "payment_amount", "is_active"]


class FormSchema(ModelSchema):
    class Meta:
        model = Form
        fields = [
            "id",
            "title",
            "description",
            "slug",
            "sections",
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

    class Meta:
        model = FormResponse
        fields = ["id", "answers", "is_paid", "submitted_at"]


class MyFormResponseSchema(ModelSchema):
    """The current user's own response."""

    class Meta:
        model = FormResponse
        fields = ["id", "answers", "is_paid", "submitted_at"]


class FormSubmitResponseSchema(Schema):
    status: str
    order: dict[str, Any] | None = None
