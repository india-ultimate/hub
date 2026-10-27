from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Lower
from django.utils.timezone import now

from server.core.models import Player
from server.duplicates.players import review
from server.duplicates.players.merge import check_blockers
from server.duplicates.players.models import ClusterMember, DuplicateCluster
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import call_api, denied, refuse
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, cap, full_name, money, slug_problem
from server.mcp.tools.staff_members import admin_url, find_season, previous_season, season_slug
from server.season.models import Season
from server.servicerequests import service
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.subscription.models import SponsorshipGrant, Subscription
from server.task.models import Task
from server.ticket.models import Ticket, TicketMessage
from server.tournament.models import Event
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransactionPlayer,
)

OLDEST = 5
STALE_CLUSTER_DAYS = 7
FAILED_TASK_DAYS = 7
REPORT_ROWS = 200
PRIVATE_LINES = {"Date of birth", "Signs in with", "Email", "Phone", "Last login"}


def _count(rows: Any, items: Any) -> dict[str, Any]:
    return {"count": rows.count(), "oldest": [items(r) for r in rows[:OLDEST]]}


@tool(
    "get_staff_inbox",
    title="Staff inbox",
    audience=Audience.STAFF,
    description=(
        "What needs staff attention, with counts and the oldest 5 of each, each with a Hub or "
        "admin link: pending service requests, payment lines needing review, failed refunds, "
        "tickets with no handler reply, duplicate groups open over 7 days, failed tasks in "
        "the last 7 days."
    ),
    input_schema={"type": "object", "additionalProperties": False},
)
def get_staff_inbox(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    stamp = now()
    handled = TicketMessage.objects.filter(ticket=OuterRef("pk"), is_deleted=False).filter(
        Q(sender__is_staff=True) | Q(sender__assigned_tickets=OuterRef("pk"))
    )
    return ok(
        {
            "service_requests": _count(
                ServiceRequest.objects.filter(status=ServiceRequestStatus.PENDING)
                .select_related("user")
                .order_by("created_at"),
                lambda r: {
                    "request_id": r.pk,
                    "type": r.type,
                    "requested_by": full_name(r.user),
                    "created_at": r.created_at.isoformat(),
                    "url": admin_url("server_servicerequest_change", r.pk),
                },
            ),
            "lines_needing_review": _count(
                RazorpayTransactionPlayer.objects.filter(needs_review=True)
                .select_related("player__user")
                .order_by("transaction__payment_date"),
                lambda line: {
                    "order_id": line.transaction_id,
                    "player_id": line.player_id,
                    "full_name": full_name(line.player.user),
                    "review_note": line.review_note,
                    "url": admin_url("server_razorpaytransaction_change", line.transaction_id),
                },
            ),
            "failed_refunds": _count(
                RazorpayRefund.objects.filter(status=RazorpayRefund.Status.FAILED).order_by("pk"),
                lambda r: {
                    "order_id": r.transaction_id,
                    **money(r.amount),
                    "error": r.error,
                    "url": admin_url("server_razorpaytransaction_change", r.transaction_id),
                },
            ),
            "open_tickets": _count(
                Ticket.objects.exclude(status=Ticket.Status.RESOLVED)
                .filter(Q(assignees=None) | ~Exists(handled))
                .distinct()
                .order_by("created_at"),
                lambda t: {
                    "ticket_id": t.pk,
                    "title": t.title,
                    "unassigned": not t.assignees.exists(),
                    "created_at": t.created_at.isoformat(),
                    "url": f"{settings.PUBLIC_URL}/tickets/{t.pk}",
                },
            ),
            "stale_duplicate_groups": _count(
                DuplicateCluster.objects.filter(
                    status__in=DuplicateCluster.OPEN_STATUSES,
                    created_at__lt=stamp - timedelta(days=STALE_CLUSTER_DAYS),
                ).order_by("created_at"),
                lambda c: {
                    "cluster_id": c.pk,
                    "status": c.status,
                    "created_at": c.created_at.isoformat(),
                    "url": admin_url("server_duplicatecluster_change", c.pk),
                },
            ),
            "failed_tasks": _count(
                Task.objects.filter(
                    failed_at__gte=stamp - timedelta(days=FAILED_TASK_DAYS)
                ).order_by("failed_at"),
                lambda t: {
                    "task_id": t.pk,
                    "type": t.type,
                    "failed_at": t.failed_at.isoformat() if t.failed_at else None,
                    "url": admin_url("server_task_change", t.pk),
                },
            ),
        }
    )


def _tier(sub: Subscription | None) -> str | None:
    return sub.tier if sub else None


@tool(
    "get_membership_report",
    title="Membership report",
    audience=Audience.STAFF,
    description=(
        "Members for a season (default: this one), up to 200 rows of player_id, full_name and "
        "tier. kind is active, not_renewed (members last season who have none this season), "
        "sponsored, or check_emails (pass emails to see which are active members; not_active "
        "lists the positions, from 1, of the emails that are not)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "season_slug": SLUG_SCHEMA,
            "kind": {
                "type": "string",
                "enum": ["active", "not_renewed", "sponsored", "check_emails"],
            },
            "emails": {
                "type": "array",
                "items": {"type": "string", "maxLength": 254},
                "maxItems": REPORT_ROWS,
            },
        },
        "required": ["kind"],
        "additionalProperties": False,
    },
)
def get_membership_report(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    season = find_season(args.get("season_slug"))
    if season is None:
        return fail("No such season", hint="Use a slug like season-2026-2027")
    kind = args["kind"]
    here = Subscription.objects.for_season(season).select_related("player__user", "plan__type")
    extra: dict[str, Any] = {}
    subs: dict[int, Subscription | None]
    if kind == "active":
        subs = {s.player_id: s for s in here.filter(is_active=True)}
    elif kind == "sponsored":
        subs = {s.player_id: s for s in here.filter(plan__type__requires_grant=True)}
        for grant in SponsorshipGrant.objects.filter(season=season):
            subs.setdefault(grant.player_id, None)
    elif kind == "check_emails":
        given = [e.strip().lower() for e in args.get("emails", [])]
        emails = [e for e in given if e]
        if not emails:
            return fail("Pass emails to check")
        found = {
            s.player.user.email.lower(): s
            for s in here.filter(is_active=True)
            .annotate(address=Lower("player__user__email"))
            .filter(address__in=emails)
        }
        subs = {s.player_id: s for s in found.values()}
        # By position in the list passed in: the addresses themselves never go back.
        extra = {"not_active": [n for n, e in enumerate(given, 1) if e and e not in found]}
    else:
        last = previous_season(season)
        kept = set(here.values_list("player_id", flat=True))
        subs = {
            s.player_id: s
            for s in Subscription.objects.for_season(last).select_related(
                "player__user", "plan__type"
            )
            if s.player_id not in kept
        }
    players = {p.pk: p for p in Player.objects.filter(pk__in=subs).select_related("user")}
    rows = sorted(
        (
            {
                "player_id": pk,
                "full_name": full_name(players[pk].user),
                "tier": _tier(sub),
            }
            for pk, sub in subs.items()
        ),
        key=lambda r: (r["full_name"], r["player_id"]),
    )
    data = {
        "season_slug": season_slug(season),
        "kind": kind,
        "count": len(rows),
        "rows": rows[:REPORT_ROWS],
        **extra,
    }
    return ok(cap(data, list_key="rows", hint="Narrow it with another season or kind"))


def _account_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": row["order_id"],
        "payment_id": row["payment_id"],
        "date": row["date"],
        "event": row["event"],
        "team": row["team"],
        "type": row["type"],
        "for": row["for"],
        "payer_name": row["payer"]["name"],
        "players": row["players"],
        **money(row["amount"]),
        "refunded": money(row["refunded"]),
        "status": row["status"],
    }


@tool(
    "get_payment_account_report",
    title="Payment account report",
    audience=Audience.ACCOUNT_VIEWER,
    description=(
        "Payments into one payment account for one tournament, with totals, as the Hub "
        "payments page shows them. event_slug defaults to the account's latest event; status is "
        "paid, refunded or all; q searches team, payer name, payment id and order id."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "account_slug": SLUG_SCHEMA,
            "event_slug": SLUG_SCHEMA,
            "status": {"type": "string", "enum": ["paid", "refunded", "all"]},
            "q": {"type": "string", "maxLength": 100},
            "page": {"type": "integer", "minimum": 1},
        },
        "required": ["account_slug"],
        "additionalProperties": False,
    },
)
def get_payment_account_report(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    query: dict[str, Any] = {k: args[k] for k in ("status", "q", "page") if k in args}
    if (slug := args.get("event_slug")) is not None:
        event = Event.objects.filter(slug=slug).first()
        if event is None:
            return fail(f"No tournament with event_slug {slug}")
        query["event"] = event.pk
    if problem := slug_problem(account_slug=args["account_slug"]):
        return problem
    response = call_api(
        ctx, "GET", f"/api/payment-accounts/{args['account_slug']}/transactions", query=query
    )
    if not response.ok:
        return denied(response)
    data = response.data
    totals = data["totals"]
    event_slugs = dict(
        Event.objects.filter(pk__in=[e["id"] for e in data["events"]]).values_list("pk", "slug")
    )
    return ok(
        cap(
            {
                "account": {
                    "account_slug": data["account"]["slug"],
                    "name": data["account"]["name"],
                },
                "event_slug": event_slugs.get(data["event"]),
                "events": [
                    {"event_slug": event_slugs.get(e["id"]), "title": e["title"]}
                    for e in data["events"]
                ],
                "totals": {
                    "collected": money(totals["collected"]),
                    "refunded": money(totals["refunded"]),
                    "net": money(totals["net"]),
                    "teams_paid": totals["teams_paid"],
                    "players_paid": totals["players_paid"],
                },
                "count": data["count"],
                "page_size": data["page_size"],
                "payments": [_account_row(r) for r in data["results"]],
            },
            list_key="payments",
            hint="Ask for the next page or narrow with q",
        )
    )


def _merge_preview(item: ServiceRequest) -> dict[str, Any] | None:
    row = ClusterMember.objects.filter(staff_request=item).select_related("user").first()
    if row is None or row.user is None:
        return None
    lines = review.compare(item.user, [row.user])
    return {
        "other_user_id": row.user.pk,
        "other_full_name": full_name(row.user),
        "compare": [
            {
                "label": line.label,
                "keeper": line.values[0],
                "other": line.values[1],
                "differs": line.differs,
            }
            for line in lines
            if line.label not in PRIVATE_LINES
        ],
        "blockers": review.in_words(check_blockers(item.user, [row.user])),
    }


def _request_row(item: ServiceRequest) -> dict[str, Any]:
    row: dict[str, Any] = {
        "request_id": item.pk,
        "type": item.type,
        "status": item.status,
        "requested_by": {"user_id": item.user_id, "full_name": full_name(item.user)},
        "message": item.message,
        "season_slug": season_slug(item.season) if item.season else None,
        "players": [
            {"player_id": p.pk, "full_name": full_name(p.user)} for p in item.service_players.all()
        ],
        "created_at": item.created_at.isoformat(),
        "admin_url": admin_url("server_servicerequest_change", item.pk),
    }
    if item.type == ServiceRequestType.REQUEST_ACCOUNT_MERGE:
        row["merge_preview"] = _merge_preview(item)
    return row


@tool(
    "list_service_requests",
    title="Service requests",
    audience=Audience.STAFF,
    description=(
        "Sponsorship and account-merge requests, pending by default. Merge requests come with "
        "a preview and blockers, and are approved on Hub only, through the admin link."
    ),
    input_schema={
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["pending", "all"]}},
        "additionalProperties": False,
    },
)
def list_service_requests(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    rows = ServiceRequest.objects.select_related("user", "season").prefetch_related(
        "service_players__user"
    )
    if args.get("status", "pending") == "pending":
        rows = rows.filter(status=ServiceRequestStatus.PENDING)
    ordered = rows.order_by("created_at")[:50]
    return ok(
        cap(
            {"requests": [_request_row(item) for item in ordered]},
            list_key="requests",
            hint="Only the oldest 50 are listed. Decide some, then ask again for the rest.",
        )
    )


@tool(
    "decide_sponsorship_request",
    title="Decide a sponsorship request",
    audience=Audience.STAFF,
    writes=True,
    destructive=True,
    emails=True,
    description=(
        "Approve or reject a pending sponsorship request. Approving gives each listed player "
        "the sponsored tier for the season. Either way the requester is emailed. Needs the "
        "permission to change service requests."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "request_id": {"type": "integer"},
            "decision": {"type": "string", "enum": ["approve", "reject"]},
        },
        "required": ["request_id", "decision"],
        "additionalProperties": False,
    },
)
def decide_sponsorship_request(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if not ctx.user.has_perm("server.change_servicerequest"):
        return refuse("you cannot change service requests.")
    item = (
        ServiceRequest.objects.select_related("user", "season")
        .filter(pk=args["request_id"], type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION)
        .first()
    )
    if item is None:
        return fail(f"No sponsorship request with request_id {args['request_id']}")
    if item.status != ServiceRequestStatus.PENDING:
        return fail(f"This request is already {item.get_status_display().lower()}.")
    approve = args["decision"] == "approve"
    names = ", ".join(full_name(p.user) for p in item.service_players.select_related("user"))
    season = item.season or Season.current()
    message = (
        f"Approve {full_name(item.user)}'s request: sponsor {names or 'nobody listed'} for "
        f"{season.name if season else 'no season'}, and email {full_name(item.user)}."
        if approve
        else f"Reject {full_name(item.user)}'s request to sponsor {names or 'nobody listed'} "
        f"and email {full_name(item.user)}."
    )

    def act() -> ToolResult:
        fresh = ServiceRequest.objects.select_for_update().get(pk=item.pk)
        if fresh.status != ServiceRequestStatus.PENDING:
            return fail("Someone else decided this request first.")
        if not approve:
            service.reject(fresh)
            return ok({"done": True, "request_id": fresh.pk, "status": "rejected"})
        granted_for, players = service.approve_sponsorship(fresh, ctx.user)
        if granted_for is None:
            return fail("There is no season to grant. Ask an admin to add one.")
        return ok(
            {
                "done": True,
                "request_id": fresh.pk,
                "status": "approved",
                "season_slug": season_slug(granted_for),
                "player_ids": [p.pk for p in players],
            }
        )

    return confirm_then(ctx, message=message, binding=args, action=act)
