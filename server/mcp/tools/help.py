from typing import Any

from django.conf import settings
from django.db.models import OuterRef, Subquery

from server.committee.models import Role, TicketRoute
from server.core.models import User
from server.mcp.dispatch import call_api, denied
from server.mcp.registry import (
    CHECKS,
    Audience,
    ToolContext,
    ToolResult,
    fail,
    ok,
    tool,
)
from server.mcp.shape import cap, full_name
from server.ticket.access import routed_to
from server.ticket.api import PAGE_SIZE, visible_tickets
from server.ticket.models import Ticket, TicketMessage

STATUSES = ["OPN", "PRG", "RES"]
SORTS = ["relevance", "newest", "upvotes"]
WAITING_SCAN = 100
ID = {"type": "integer", "minimum": 1}
NO_TICKET = "Ticket not found, or you can't see it."


def _summary(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticket_id": ticket["id"],
        "url": f"{settings.PUBLIC_URL}/tickets/{ticket['id']}",
        "title": ticket["title"],
        "status": ticket["status"],
        "priority": ticket["priority"],
        "category": ticket["category"],
        "category_name": ticket["category_name"],
        "is_private": ticket["is_private"],
        "upvote_count": ticket["upvote_count"],
        "has_upvoted": ticket["has_upvoted"],
        "created_at": ticket["created_at"],
        "created_by": full_name(ticket["created_by"]),
        "assignees": [full_name(a) for a in ticket["assignees"]],
        "message_count": ticket["message_count"],
    }


def _thread(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        **_summary({**ticket, "message_count": len(ticket["messages"])}),
        "description": ticket["description"],
        "can_handle": ticket["can_handle"],
        "can_edit": ticket["can_edit"],
        "messages": [
            {
                "message_id": m["id"],
                "from": full_name(m["sender"]),
                "at": m["created_at"],
                "text": m["message"],
                "has_attachment": bool(m["attachment"]),
            }
            for m in ticket["messages"]
            if not m["is_deleted"]
        ],
    }


def _waiting_on_us(ctx: ToolContext, category: str | None) -> ToolResult:
    if not CHECKS[Audience.HANDLER](ctx.user):
        return fail("waiting_on_us is for staff and committee members who handle tickets.")
    queue = visible_tickets(ctx.user).filter(
        status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]
    )
    if not ctx.user.is_staff:
        queue = queue.filter(routed_to(ctx.user))
    if category:
        queue = queue.filter(category__key=category)
    last = TicketMessage.objects.filter(ticket=OuterRef("pk"), is_deleted=False).order_by(
        "-created_at", "-id"
    )
    queue = queue.annotate(
        last_sender=Subquery(last.values("sender_id")[:1]),
        last_at=Subquery(last.values("created_at")[:1]),
    ).order_by("-created_at", "-id")
    total = queue.count()
    tickets = list(queue[:WAITING_SCAN])
    senders = {t.last_sender for t in tickets if t.last_sender}
    staff = set(User.objects.filter(pk__in=senders, is_staff=True).values_list("pk", flat=True))
    held: dict[int, set[int]] = {}
    for user_id, committee_id in (
        Role.objects.current().filter(user__in=senders).values_list("user_id", "committee_id")
    ):
        held.setdefault(user_id, set()).add(committee_id)
    routed: dict[str, set[int]] = {}
    for route_category, committee_id in TicketRoute.objects.filter(
        category__in={t.category_id for t in tickets if t.category_id}
    ).values_list("category__key", "committee_id"):
        routed.setdefault(route_category, set()).add(committee_id)

    def answered(ticket: Any) -> bool:
        sender = ticket.last_sender
        return bool(sender) and (
            sender in staff or bool(held.get(sender, set()) & routed.get(ticket.category_id, set()))
        )

    waiting = [
        {
            "ticket_id": t.pk,
            "url": f"{settings.PUBLIC_URL}/tickets/{t.pk}",
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "category": t.category_id,
            "created_at": t.created_at.isoformat(),
            "last_message_at": (t.last_at or t.created_at).isoformat(),
        }
        for t in tickets
        if not answered(t)
    ]
    out = {"tickets": waiting, "scanned": min(total, WAITING_SCAN), "open_tickets": total}
    return ok(cap(out, list_key="tickets", hint="Filter by category."))


@tool(
    "list_tickets",
    title="List help tickets",
    description=(
        "Hub help tickets you may see (public ones, your own, and those routed to your "
        "committees), 20 a page, newest first, each with its Hub url. Filter by q (words), "
        "status (OPN open, PRG in progress, RES resolved), category key, mine (raised by you), "
        "assigned (assigned to you) and sort. Handlers (staff and committee members) can set "
        "waiting_on_us=true for open tickets in their queue whose latest message is not from a "
        "handler; that looks at the newest 100 open tickets. Tickets are read-only here: to "
        "reply, triage or upvote, send the user to the ticket's Hub page (url); to raise one, "
        "send them to "
        f"{settings.PUBLIC_URL}/tickets/new."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "q": {"type": "string", "maxLength": 200},
            "status": {"type": "array", "items": {"type": "string", "enum": STATUSES}},
            "category": {"type": "string", "maxLength": 100},
            "mine": {"type": "boolean"},
            "assigned": {"type": "boolean"},
            "sort": {"type": "string", "enum": SORTS},
            "page": {"type": "integer", "minimum": 1},
            "waiting_on_us": {"type": "boolean"},
        },
        "additionalProperties": False,
    },
)
def list_tickets(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if args.get("waiting_on_us"):
        return _waiting_on_us(ctx, args.get("category"))
    page = args.get("page", 1)
    query = {k: v for k, v in args.items() if k != "page" and v not in ("", None, [])}
    response = call_api(ctx, "GET", "/api/ticket/", query={**query, "page": page})
    if not response.ok:
        return denied(response)
    total = response.data["count"]
    out = {
        "tickets": [_summary(t) for t in response.data["items"]],
        "total": total,
        "page": page,
        "has_more": page * PAGE_SIZE < total,
    }
    return ok(cap(out, list_key="tickets", hint="Ask for the next page or narrow the search."))


@tool(
    "get_ticket",
    title="Read a help ticket",
    description=(
        "A help ticket by ticket_id: its description and the conversation, each message with "
        "message_id, from, at, text and has_attachment. Read-only: to open attachments, reply, "
        "triage or upvote, send the user to its Hub page (url)."
    ),
    input_schema={
        "type": "object",
        "properties": {"ticket_id": ID},
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
)
def get_ticket(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    response = call_api(ctx, "GET", f"/api/ticket/{args['ticket_id']}")
    if not response.ok:
        return denied(response, NO_TICKET)
    thread = _thread(response.data)
    messages = thread["messages"]
    if not messages:
        return ok(thread)
    # cap keeps the head of the list, so the newest go right after the first
    shuffled = {**thread, "messages": [messages[0], *reversed(messages[1:])]}
    capped = cap(
        shuffled,
        list_key="messages",
        hint="The first message and the newest ones are shown; older ones in between are left out.",
    )
    kept = capped["messages"]
    capped["messages"] = kept[:1] + kept[:0:-1]
    return ok(capped)
