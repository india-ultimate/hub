from typing import Any

from server.core.models import User
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import ApiResponse, call_api, denied, refuse
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import full_name
from server.ticket.access import can_handle
from server.ticket.api import visible_tickets

IDS = {"type": "array", "items": {"type": "integer"}, "maxItems": 10}


def _ticket(response: ApiResponse) -> dict[str, Any]:
    data = response.data
    return {
        "ticket_id": data["id"],
        "title": data["title"],
        "status": data["status"],
        "priority": data["priority"],
        "category": data["category"],
        "assignees": [{"user_id": a["id"], "full_name": full_name(a)} for a in data["assignees"]],
    }


def _apply(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    path = f"/api/ticket/{args['ticket_id']}"
    changes: dict[str, Any] = {k: args[k] for k in ("status", "priority", "category") if k in args}
    response = None
    if changes:
        response = call_api(ctx, "PUT", path, body=changes)
        if not response.ok:
            return denied(response)
    for method, key in (("DELETE", "remove_assignee_user_ids"), ("POST", "add_assignee_user_ids")):
        for user_id in args.get(key, []):
            response = call_api(ctx, method, f"{path}/assignees/{user_id}")
            if not response.ok:
                return denied(response)
    return ok(_ticket(response)) if response else fail("Nothing to change")


@tool(
    "update_ticket",
    title="Update a ticket",
    description=(
        "Triage a ticket routed to your committee: set its status (OPN open, PRG in progress, "
        "RES resolved) or priority (LOW, MED, HIG, URG), or add and remove the people handling "
        "it. Only staff can change the category. It asks first; adding someone emails them."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "integer", "minimum": 1},
            "status": {"type": "string", "enum": ["OPN", "PRG", "RES"]},
            "priority": {"type": "string", "enum": ["LOW", "MED", "HIG", "URG"]},
            "category": {"type": "string", "minLength": 1, "maxLength": 100},
            "add_assignee_user_ids": IDS,
            "remove_assignee_user_ids": IDS,
        },
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
    audience=Audience.HANDLER,
    writes=True,
    emails=True,
)
def update_ticket(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if len(args) == 1 + ("confirmation" in args):
        return fail("Nothing to change: give a status, priority, category or assignees.")
    if "category" in args and not ctx.user.is_staff:
        return refuse("only staff can change a ticket's category.")
    ticket = visible_tickets(ctx.user).filter(pk=args["ticket_id"]).first()
    if ticket is None:
        return fail("Ticket not found")
    if not can_handle(ctx.user, ticket):
        return refuse("only staff and the committees its category goes to can triage it.")
    adds = args.get("add_assignee_user_ids", [])
    removes = args.get("remove_assignee_user_ids", [])
    people = {u.pk: u for u in User.objects.filter(pk__in=[*adds, *removes])}
    if missing := [i for i in [*adds, *removes] if i not in people]:
        return fail(f"No Hub user with user_id {missing[0]}")

    def named(ids: list[int]) -> str:
        return ", ".join((full_name(people[i]) or f"user {i}") for i in ids)

    changes = [f"{key} {args[key]}" for key in ("status", "priority", "category") if key in args]
    if removes:
        changes.append(f"unassign {named(removes)}")
    if adds:
        changes.append(f"assign {named(adds)}, who are emailed")
    return confirm_then(
        ctx,
        message=f"Change ticket #{ticket.pk}: {'; '.join(changes)}?",
        binding=args,
        action=lambda: _apply(ctx, args),
        emails=len(adds),
    )
