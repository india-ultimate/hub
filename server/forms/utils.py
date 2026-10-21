import csv
import io
import time
from typing import Any

from django.conf import settings
from django.core import mail
from django.db.models import QuerySet

from server.transaction.client import razorpay
from server.transaction.models import AuthenticatedHttpRequest, RazorpayTransaction

from .models import CHOICE_FIELD_TYPES, FieldType, Form, FormResponse


def format_answer_for_csv(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def build_responses_csv(form: Form, responses: QuerySet[FormResponse] | list[FormResponse]) -> str:
    """Build a CSV string of form responses for staff download."""
    field_defs = form.fields or []
    headers = ["Name", "Email", "Phone", "Submitted"] + [
        str(f.get("label") or f.get("key") or "") for f in field_defs
    ]
    field_keys = [str(f.get("key") or "") for f in field_defs]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for response in responses:
        answers = response.answers or {}
        row = [
            response.user.get_full_name(),
            response.user.email,
            response.user.phone,
            response.submitted_at.isoformat(sep=" ", timespec="seconds"),
        ]
        row.extend(format_answer_for_csv(answers.get(key)) for key in field_keys)
        writer.writerow(row)
    return buffer.getvalue()


def validate_structure(sections: list[dict[str, Any]], fields: list[dict[str, Any]]) -> str | None:
    """Check section keys and branching targets of a form being saved.

    Returns an error message, or None if the structure is valid.
    """
    keys = [s["key"] for s in sections]
    if any(not key for key in keys):
        return "Section keys cannot be empty"
    if len(set(keys)) != len(keys):
        return "Section keys must be unique"
    index = {key: i for i, key in enumerate(keys)}

    for section in sections:
        target = section.get("next", "")
        if target not in ("", "submit") and index.get(target, -1) <= index[section["key"]]:
            return f"Section '{section['key']}' must continue to a later section"

    branching: set[str] = set()
    for field in fields:
        label = field.get("label") or field.get("key")
        section = field.get("section", "")
        goto = field.get("goto") or {}
        if not sections:
            if section or goto:
                return f"Question '{label}' cannot have a section or branching without sections"
            continue
        if section not in index:
            return f"Question '{label}' is in an unknown section"
        if not goto:
            continue
        if field.get("type") not in (FieldType.RADIO, FieldType.DROPDOWN):
            return f"Question '{label}' cannot branch; only single choice and dropdown can"
        if section in branching:
            return f"Section '{section}' has more than one branching question"
        branching.add(section)
        options = field.get("options") or []
        for option, target in goto.items():
            if option not in options:
                return f"Question '{label}' branches on '{option}', which is not an option"
            if target not in ("", "submit") and index.get(target, -1) <= index[section]:
                return f"Question '{label}' must go to a later section for '{option}'"
    return None


def group_sections(form: Form) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Pair each section with its fields; a form without sections is one implicit section."""
    if not form.sections:
        return [({"key": "", "next": ""}, form.fields)]
    return [
        (section, [f for f in form.fields if f.get("section", "") == section["key"]])
        for section in form.sections
    ]


def path_fields(form: Form, answers: dict[str, Any]) -> list[dict[str, Any]]:
    """The fields a responder with these answers passes through, in order."""
    groups = group_sections(form)
    index_of = {section["key"]: i for i, (section, _) in enumerate(groups)}
    path: list[dict[str, Any]] = []
    i = 0
    while i < len(groups):
        section, fields = groups[i]
        path.extend(fields)
        target = section.get("next", "")
        for field in fields:
            answer = answers.get(field["key"])
            if field.get("goto") and isinstance(answer, str):
                target = field["goto"].get(answer, "") or target
        if target == "submit":
            break
        i = index_of[target] if target in index_of and index_of[target] > i else i + 1
    return path


def validate_answers(form: Form, answers: dict[str, Any]) -> str | None:
    """Validate submitted answers against the fields on the responder's path.

    Returns an error message, or None if the answers are valid.
    """
    for field in path_fields(form, answers):
        key = field["key"]
        label = field.get("label", key)
        field_type = field.get("type")
        required = field.get("required", False)
        value = answers.get(key)

        is_empty = value is None or value in ("", [])
        if required and is_empty:
            return f"'{label}' is required."

        if is_empty:
            continue

        if field_type in CHOICE_FIELD_TYPES:
            options = field.get("options", [])
            if field_type == FieldType.CHECKBOX:
                if not isinstance(value, list):
                    return f"'{label}' must be a list of choices."
                invalid = [v for v in value if v not in options]
            else:
                invalid = [value] if value not in options else []
            if invalid:
                return f"'{label}' has invalid choice(s): {', '.join(map(str, invalid))}."

    return None


def send_form_submission_email(response: FormResponse) -> None:
    """Email the responder a copy of all their answers."""
    form = response.form
    user = response.user
    if not user.email:
        return

    subject = f"Your submission to {form.title}"

    lines = [f"Thanks for your submission to '{form.title}'. Here is a copy of your answers:", ""]
    for field in form.fields:
        label = field.get("label", field.get("key"))
        value = response.answers.get(field.get("key"))
        if isinstance(value, list):
            value = ", ".join(map(str, value))
        lines.append(f"{label}: {value if value not in (None, '') else '-'}")
    plain_message = "\n".join(lines)

    mail.send_mail(
        subject,
        plain_message,
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=True,
    )


def create_form_payment_order(
    request: AuthenticatedHttpRequest, form: Form, response: FormResponse
) -> dict[str, Any] | None:
    """Create a Razorpay order for a paid form submission, reusing the Razorpay
    client and the RazorpayTransaction model. Links the transaction to the
    pending response. Returns the order data (RazorpayOrderSchema shape) or None.
    """
    user = request.user
    ts = round(time.time())
    # Guarded by Form.needs_payment at the call site; default keeps mypy happy.
    amount = form.payment_amount or 0

    receipt = f"form:{form.id}:{response.id}:{ts}"
    notes: dict[str, int | str] = {
        "user_id": user.id,
        "form_id": form.id,
        "response_id": response.id,
    }

    data = razorpay.create_order(amount, receipt=receipt, notes=notes)
    if data is None:
        return None

    # The transaction record needs model instances; create_from_order_data only
    # keeps keys that match model fields (and handles `players` separately).
    transaction = RazorpayTransaction.create_from_order_data(
        {
            **data,
            "user": user,
            "players": [],
            "amount": amount,
            "type": RazorpayTransaction.TransactionTypeChoices.FORM_PAYMENT,
        }
    )

    response.transaction = transaction
    response.save(update_fields=["transaction"])

    description = f"Payment by {user.get_full_name()} for form: {form.title}"
    if len(description) > razorpay.RAZORPAY_DESCRIPTION_MAX:
        description = description[:250] + "..."

    # Return a clean, JSON-serializable order (RazorpayOrderSchema shape) for the
    # frontend Razorpay checkout — no model instances.
    return {
        "order_id": data["order_id"],
        "amount": amount,
        "currency": data["currency"],
        "receipt": data["receipt"],
        "key": data["key"],
        "name": settings.APP_NAME,
        "image": settings.LOGO_URL,
        "description": description,
        "prefill": {"name": user.get_full_name(), "email": user.email, "contact": user.phone},
    }


def mark_form_response_paid(transaction: RazorpayTransaction) -> None:
    """Mark the form response tied to a completed transaction as paid and email
    the responder a copy of their answers."""
    try:
        response = FormResponse.objects.get(transaction=transaction)
    except FormResponse.DoesNotExist:
        return

    if response.is_paid:
        return

    response.is_paid = True
    response.save(update_fields=["is_paid"])
    send_form_submission_email(response)
