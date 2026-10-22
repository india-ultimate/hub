from http import HTTPStatus
from typing import Any

from server.forms.models import Form
from server.forms.utils import path_fields, validate_answers
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import ApiResponse, call_api, denied
from server.mcp.pay import pay_link
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, money, slug_problem
from server.receipts.money import rupees

HOW_TO_ANSWER = (
    "answers maps each field key to its value: text, textarea, email and date (YYYY-MM-DD) "
    "take a string, number a number, radio and dropdown one of the options, checkbox a "
    "list of options. Only questions on the path the answers take are asked."
)


def _failed(response: ApiResponse) -> ToolResult:
    if response.status == HTTPStatus.BAD_GATEWAY:
        return fail("Hub could not reach the payment service. Try again shortly.")
    return denied(response)


def _branching(form: dict[str, Any]) -> list[str]:
    titles = {s["key"]: s.get("title") or s["key"] for s in form["sections"]}
    lines = []
    for field in form["fields"]:
        for option, target in (field.get("goto") or {}).items():
            where = (
                "submits the form"
                if target == "submit"
                else f"jumps to section '{titles.get(target, target)}'"
            )
            lines.append(
                f"Question '{field.get('label', field['key'])}': answering '{option}' {where}; "
                "any other answer goes to the next section."
            )
    return lines


@tool(
    "list_forms",
    title="List Hub forms",
    description=(
        "Forms open for answers on Hub (sign-ups, surveys, paid registrations), each with "
        "form_slug, title and the price if it has one. Read one with get_form."
    ),
    input_schema={"type": "object", "additionalProperties": False},
)
def list_forms(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    response = call_api(ctx, "GET", "/api/forms/")
    if not response.ok:
        return denied(response)
    forms = [
        {
            "form_slug": f["slug"],
            "title": f["title"],
            "description": f["description"],
            **money(f["payment_amount"] or None),
        }
        for f in response.data
        if f["is_active"]
    ]
    return ok(cap({"forms": forms}, list_key="forms", hint="Ask about one form by name."))


@tool(
    "get_form",
    title="Read a Hub form",
    description=(
        "A form by form_slug: its sections and questions (key, label, type, required, options) "
        "and where each branching answer leads. Read this before submit_form. A closed form "
        "has accepting_answers=false."
    ),
    input_schema={
        "type": "object",
        "properties": {"form_slug": SLUG_SCHEMA},
        "required": ["form_slug"],
        "additionalProperties": False,
    },
)
def get_form(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(form_slug=args["form_slug"]):
        return problem
    response = call_api(ctx, "GET", f"/api/forms/{args['form_slug']}")
    if not response.ok:
        return denied(response)
    form = response.data
    return ok(
        {
            "form_slug": form["slug"],
            "title": form["title"],
            "description": form["description"],
            **money(form["payment_amount"] or None),
            "accepting_answers": form["is_active"],
            "sections": [
                {
                    "section_key": s["key"],
                    "title": s.get("title", ""),
                    "description": s.get("description", ""),
                    "next": s.get("next", ""),
                }
                for s in form["sections"]
            ],
            "fields": [
                {
                    "key": f["key"],
                    "label": f.get("label", f["key"]),
                    "type": f.get("type", "text"),
                    "required": f.get("required", False),
                    "options": f.get("options", []),
                    "section": f.get("section", ""),
                    "goto": f.get("goto", {}),
                }
                for f in form["fields"]
            ],
            "branching": _branching(form),
            "how_to_answer": HOW_TO_ANSWER,
        }
    )


@tool(
    "submit_form",
    title="Submit a Hub form",
    description=(
        "Answer a form as the user, by form_slug and answers (see get_form). A free form is "
        "submitted and Hub emails the user a copy. A paid form returns pay_url: the user pays "
        "there, and the answer counts only once paid. Hub asks the user to confirm first."
    ),
    input_schema={
        "type": "object",
        "properties": {"form_slug": SLUG_SCHEMA, "answers": {"type": "object"}},
        "required": ["form_slug", "answers"],
        "additionalProperties": False,
    },
    writes=True,
    emails=True,
)
def submit_form(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if problem := slug_problem(form_slug=args["form_slug"]):
        return problem
    form = Form.objects.filter(slug=args["form_slug"], is_active=True).first()
    if form is None:
        return fail("Form does not exist or is not active")
    if wrong := validate_answers(form, args["answers"]):
        return fail(wrong)
    given = [
        f"{f['label']}: {args['answers'][f['key']]}"
        for f in path_fields(form, args["answers"])
        if f["key"] in args["answers"]
    ]
    if form.needs_payment:
        paid = f"It costs {rupees(form.payment_amount or 0)}: you get a link to pay, and the answer counts once paid."
    else:
        paid = "Hub emails you a copy."

    def submit() -> ToolResult:
        response = call_api(
            ctx,
            "POST",
            f"/api/forms/{args['form_slug']}/responses",
            body={"answers": args["answers"]},
        )
        if not response.ok:
            return _failed(response)
        order = response.data.get("order")
        if not order:
            return ok({"done": True, "status": "submitted", "form_slug": args["form_slug"]})
        return ok(
            {
                "done": True,
                "status": "payment_required",
                "form_slug": args["form_slug"],
                "order_id": order["order_id"],
                **money(order["amount"] or None),
                "pay_url": pay_link(order["order_id"]),
            }
        )

    return confirm_then(
        ctx,
        message=f'Submit "{form.title}" with these answers? {paid}\n\n' + "\n".join(given),
        binding=args,
        action=submit,
    )
