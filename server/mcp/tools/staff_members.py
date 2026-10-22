from typing import Any

from django.conf import settings
from django.db.models import Q, Value
from django.db.models.functions import Concat
from django.urls import reverse
from django.utils.text import slugify

from server.core.models import Player
from server.duplicates.identity import mask_email
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import SLUG_SCHEMA, full_name, money
from server.season.models import Season
from server.subscription import eligibility
from server.subscription.models import Subscription
from server.subscription.sponsorship import has_grant
from server.tournament.models import Event
from server.transaction.models import (
    RazorpayRefund,
    RazorpayTransaction,
    RazorpayTransactionPlayer,
)
from server.utils import today

MIN_REASON = 5
FIND_LIMIT = 10
PAYMENT_LIMIT = 10


def admin_url(name: str, *args: Any) -> str:
    return settings.PUBLIC_URL + reverse(f"admin:{name}", args=args)


def season_slug(season: Season) -> str:
    return slugify(season.name)


def find_season(slug: str | None) -> Season | None:
    if slug is None:
        return Season.current()
    return next((s for s in Season.objects.all() if season_slug(s) == slug), None)


def previous_season(season: Season) -> Season | None:
    return Season.objects.filter(end_date__lt=season.start_date).order_by("-end_date").first()


def _mask_phone(phone: str) -> str:
    return "*" * max(len(phone) - 4, 0) + phone[-4:]


@tool(
    "find_member",
    title="Find a member",
    audience=Audience.STAFF,
    description=(
        "Search players by name, email, phone or IU id (up to 10). Email and phone are masked. "
        "Set reveal to true with a reason of at least 5 characters to see them in full; the "
        "reason and the people revealed are written to the audit log. "
        "Don't put contact details in the reason; it is logged."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 2, "maxLength": 100},
            "reveal": {"type": "boolean"},
            "reason": {"type": "string", "maxLength": 300},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
def find_member(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    reveal = bool(args.get("reveal"))
    reason = str(args.get("reason", "")).strip()
    if reveal and len(reason) < MIN_REASON:
        return fail("Say why you need the contact details: reason must be at least 5 characters.")
    text = args["query"]
    players = list(
        Player.objects.select_related("user")
        .annotate(full_name=Concat("user__first_name", Value(" "), "user__last_name"))
        .filter(
            Q(full_name__icontains=text)
            | Q(user__email__icontains=text)
            | Q(user__phone__icontains=text)
            | Q(iu_id__icontains=text)
        )
        .order_by("user__first_name", "user__last_name", "pk")[:FIND_LIMIT]
    )
    if reveal:
        ctx.audit["reveal"] = {"reason": reason, "player_ids": [p.pk for p in players]}
    return ok(
        {
            "members": [
                {
                    "player_id": p.pk,
                    "user_id": p.user_id,
                    "full_name": full_name(p.user),
                    "iu_id": p.iu_id,
                    "city": p.city,
                    "email": p.user.email if reveal else mask_email(p.user.email),
                    "phone": p.user.phone if reveal else _mask_phone(p.user.phone),
                    "revealed": reveal,
                }
                for p in players
            ],
        }
    )


def _subscription_row(sub: Subscription) -> dict[str, Any]:
    return {
        "season_slug": season_slug(sub.season),
        "tier": sub.tier,
        "is_active": sub.is_active,
        "waiver_valid": sub.waiver_valid,
        "coc_agreed": sub.coc_agreed,
        "start_date": sub.start_date.isoformat(),
        "end_date": sub.end_date.isoformat(),
        "refunded_at": sub.refunded_at.isoformat() if sub.refunded_at else None,
        **money(sub.amount_paid or 0),
    }


def _why_inactive(season: Season | None, subs: list[Subscription]) -> list[str]:
    if season is None:
        return ["No season covers today, so no membership can be active."]
    mine = [s for s in subs if s.season_id == season.pk]
    live = next((s for s in mine if s.refunded_at is None), None)
    if live is None:
        if mine:
            return [f"The {season.name} membership was refunded on {mine[0].refunded_at:%d %b %Y}."]
        return [f"No membership for {season.name}."]
    reasons = []
    if not live.is_active:
        expired = live.end_date < today()
        reasons.append(
            f"The membership expired on {live.end_date:%d %b %Y}."
            if expired
            else "The membership is switched off though it has not expired."
        )
    if not live.waiver_valid:
        reasons.append("The waiver is not signed.")
    if not live.coc_agreed:
        reasons.append("The code of conduct is not agreed.")
    return reasons


def _line_row(line: RazorpayTransactionPlayer) -> dict[str, Any]:
    return {
        "order_id": line.transaction_id,
        "type": line.transaction.type,
        "status": line.transaction.status,
        "plan": str(line.plan) if line.plan else None,
        **money(line.amount or 0),
        "needs_review": line.needs_review,
        "review_note": line.review_note,
    }


def _refund_row(refund: RazorpayRefund) -> dict[str, Any]:
    return {
        "order_id": refund.transaction_id,
        "status": refund.status,
        "source": refund.source,
        "line_player_id": refund.line.player_id if refund.line else None,
        **money(refund.amount),
        "reason": refund.reason,
        "error": refund.error,
        "created_at": refund.created_at.isoformat(),
    }


def _documents(player: Player, current: Subscription | None) -> dict[str, Any]:
    college = getattr(player, "college_id", None)
    vaccination = getattr(player, "vaccination", None)
    accreditation = getattr(player, "accreditation", None)
    return {
        "waiver_valid": bool(current and current.waiver_valid),
        "coc_agreed": bool(current and current.coc_agreed),
        "accreditation_valid": bool(accreditation and accreditation.is_valid),
        "college_id": {
            "present": college is not None,
            "expiry": college.expiry.isoformat() if college else None,
            "active": bool(college and not college.images_removed_at and college.expiry >= today()),
        },
        "vaccination": {
            "present": vaccination is not None,
            "has_certificate": bool(vaccination and vaccination.certificate),
        },
    }


@tool(
    "get_member_status",
    title="Why is this membership not active",
    audience=Audience.STAFF,
    description=(
        "A plain-English account of one player's membership: subscriptions this and last "
        "season, why this season's is not active, their payment lines (with review notes), "
        "refunds, sponsorship grant, documents, and whether they may play at event_slug."
    ),
    input_schema={
        "type": "object",
        "properties": {"player_id": {"type": "integer"}, "event_slug": SLUG_SCHEMA},
        "required": ["player_id"],
        "additionalProperties": False,
    },
)
def get_member_status(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    player = Player.objects.select_related("user").filter(pk=args["player_id"]).first()
    if player is None:
        return fail(f"No player with player_id {args['player_id']}")
    event = None
    if (slug := args.get("event_slug")) is not None:
        event = Event.objects.filter(slug=slug).first()
        if event is None:
            return fail(f"No tournament with event_slug {slug}")
    current_season = Season.current()
    seasons = [s for s in (current_season, current_season and previous_season(current_season)) if s]
    subs = list(
        Subscription.objects.filter(player=player, season__in=seasons)
        .select_related("season", "plan__type")
        .order_by("-season__start_date")
    )
    live = next(
        (
            s
            for s in subs
            if current_season and s.season_id == current_season.pk and not s.refunded_at
        ),
        None,
    )
    reasons = _why_inactive(current_season, subs)
    lines = list(
        RazorpayTransactionPlayer.objects.filter(player=player)
        .select_related("transaction", "plan__type")
        .order_by("-transaction__payment_date")[:20]
    )
    refunds = list(
        RazorpayRefund.objects.filter(
            Q(line__player=player)
            | Q(transaction__in=[line.transaction_id for line in lines], line__isnull=True)
        )
        .select_related("line")
        .order_by("-pk")[:20]
    )
    check = eligibility.check(player, event, is_playing=True) if event else None
    return ok(
        {
            "player_id": player.pk,
            "full_name": full_name(player.user),
            "season_slug": season_slug(current_season) if current_season else None,
            "is_active": not reasons,
            "why_not_active": reasons,
            "subscriptions": [_subscription_row(s) for s in subs],
            "sponsorship_granted": has_grant(player, current_season),
            "payment_lines": [_line_row(line) for line in lines],
            "refunds": [_refund_row(r) for r in refunds],
            "documents": _documents(player, live),
            "eligibility": (
                None
                if event is None
                else {
                    "event_slug": event.slug,
                    "can_play": check is None,
                    "reason": check["message"] if check else None,
                }
            ),
            "admin_url": admin_url("server_player_change", player.pk),
        }
    )


def _transaction_row(txn: RazorpayTransaction) -> dict[str, Any]:
    lines = list(txn.razorpaytransactionplayer_set.select_related("player__user", "plan"))
    refunds = list(txn.refunds.all())
    standing = sum(r.amount for r in refunds if r.status != RazorpayRefund.Status.FAILED)
    flags = []
    if any(line.needs_review for line in lines):
        flags.append("A line needs review")
    if any(r.status == RazorpayRefund.Status.FAILED for r in refunds):
        flags.append("A refund failed")
    if txn.status not in RazorpayTransaction.SETTLED:
        flags.append(f"Not paid: status is {txn.status}")
    return {
        "order_id": txn.order_id,
        "payment_id": txn.payment_id,
        "status": txn.status,
        "type": txn.type,
        "date": txn.payment_date.isoformat(),
        "event_slug": txn.event.slug if txn.event else None,
        "team_name": txn.team.name if txn.team else None,
        "payer": {"user_id": txn.user_id, "full_name": full_name(txn.user)},
        **money(txn.amount),
        "refunded": money(standing),
        "lines": [
            {
                "player_id": line.player_id,
                "full_name": full_name(line.player.user),
                "plan": str(line.plan) if line.plan else None,
                **money(line.amount or 0),
                "needs_review": line.needs_review,
                "review_note": line.review_note,
            }
            for line in lines
        ],
        "receipts": [
            {"number": r.number, "kind": r.kind, **money(r.total)} for r in txn.receipts.all()
        ],
        "refund_records": [_refund_row(r) for r in refunds],
        "flags": flags,
        "admin_links": {
            "transaction": admin_url("server_razorpaytransaction_change", txn.order_id),
            "refund_order": admin_url("refund_order", txn.order_id),
            "refund_lines": [
                {"player_id": line.player_id, "url": admin_url("refund_line", line.pk)}
                for line in lines
                if line.amount
            ],
        },
    }


@tool(
    "lookup_payment",
    title="Look up a payment",
    audience=Audience.STAFF,
    description=(
        "Find payments by order_id, payment_id or the payer's email (up to 10, newest first), "
        "with their lines, receipts, refunds, flags and admin links. It never refunds: use the "
        "admin links for that."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "minLength": 1, "maxLength": 255},
            "payment_id": {"type": "string", "minLength": 1, "maxLength": 255},
            "email": {"type": "string", "minLength": 3, "maxLength": 254},
        },
        "additionalProperties": False,
    },
)
def lookup_payment(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    filters = {
        "order_id": "order_id",
        "payment_id": "payment_id",
        "email": "user__email__iexact",
    }
    given = [key for key in filters if key in args]
    if len(given) != 1:
        return fail("Give exactly one of order_id, payment_id or email.")
    rows = (
        RazorpayTransaction.objects.filter(**{filters[given[0]]: args[given[0]]})
        .select_related("user", "event", "team")
        .order_by("-payment_date")
    )
    return ok({"payments": [_transaction_row(t) for t in rows[:PAYMENT_LIMIT]]})
