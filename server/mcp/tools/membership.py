from typing import Any

from server.core.models import Guardianship, Player
from server.mcp.confirm import confirm_then
from server.mcp.dispatch import call_api, denied
from server.mcp.pay import pay_link, receipt_link, unpaid_membership
from server.mcp.registry import ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import cap, full_name, money
from server.receipts.money import rupees
from server.season.models import Season
from server.subscription import catalog
from server.subscription.models import Subscription
from server.subscription.sponsorship import has_grant
from server.transaction.models import RazorpayTransaction
from server.transaction.schema import SubscriptionOrderItem, SubscriptionOrderSchema
from server.transaction.utils import ValidationError, build_subscription_order

MAX_PLAYERS = 10
MAX_MESSAGE = 1000
KINDS = ["receipts", "orders", "unpaid"]
HINT = "Ask for one kind (receipts, orders or unpaid) to see fewer rows."
PLAYER_IDS = {
    "type": "array",
    "items": {"type": "integer"},
    "maxItems": MAX_PLAYERS,
}


def _own_ids(ctx: ToolContext) -> list[int]:
    mine = Player.objects.filter(user=ctx.user).values_list("id", flat=True)
    wards = Guardianship.objects.filter(user=ctx.user).values_list("player_id", flat=True)
    return [*mine, *wards]


def _options(season: Season, player: Player) -> tuple[list[dict[str, Any]], str | None]:
    options, reason = [], None
    held = Subscription.objects.filter(player=player, season=season).live().first()
    paid = max(held.amount_paid or 0, held.plan.amount if held.plan else 0) if held else 0
    for plan in catalog.plans_for(season):
        slug = plan.type.slug
        if plan.type.requires_grant and not has_grant(player, season):
            if plan.amount <= paid:
                continue
            options.append(
                {
                    "tier": slug,
                    "name": plan.type.name,
                    **money(plan.amount - (held.amount_paid or 0) if held else plan.amount),
                    "kind": "upgrade" if held else "new",
                    "needs_grant": True,
                }
            )
            continue
        try:
            _, [(_, priced)] = build_subscription_order(
                SubscriptionOrderSchema(
                    season_id=season.id,
                    items=[SubscriptionOrderItem(player_id=player.id, plan_type=slug)],
                )
            )
        except ValidationError as error:
            reason = reason or str(error)
            continue
        options.append(
            {
                "tier": slug,
                "name": plan.type.name,
                **money(priced.amount),
                "kind": priced.kind,
                "needs_grant": False,
            }
        )
    return options, None if options else reason


@tool(
    "get_membership_options",
    title="Membership options and prices",
    description=(
        "The membership tiers each person can buy this season, priced for them: a new "
        "membership, or an upgrade that costs the difference. Defaults to the signed-in user and "
        "their wards. Pass player_ids to price anyone else: anyone may buy for anyone, and for "
        "other people only the name and prices are shown. A tier with needs_grant true has to be "
        "approved first, see request_sponsorship."
    ),
    input_schema={
        "type": "object",
        "properties": {"player_ids": PLAYER_IDS},
        "additionalProperties": False,
    },
)
def get_membership_options(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    season = Season.current()
    if season is None:
        return fail("No season is running right now.")
    own = _own_ids(ctx)
    ids = args.get("player_ids") or own
    found = {p.id: p for p in Player.objects.filter(id__in=ids).select_related("user")}
    if missing := [i for i in ids if i not in found]:
        return fail(f"No players with player_id {missing}")
    players = []
    for player_id in dict.fromkeys(ids):
        player = found[player_id]
        options, reason = _options(season, player)
        entry: dict[str, Any] = {"player_id": player_id, "full_name": full_name(player.user)}
        if player_id in own:
            held = Subscription.objects.filter(player=player, season=season).live().first()
            entry["current_tier"] = held.plan.type.name if held and held.plan else None
        players.append({**entry, "options": options, "not_available_reason": reason})
    return ok({"season": season.name, "players": players})


def quote_items(
    items: list[dict[str, Any]],
) -> tuple[Season, list[dict[str, Any]]] | str:
    """The season and each line priced right now, or why the order cannot be made."""
    season = Season.current()
    if season is None:
        return "No season is running right now."
    try:
        order = SubscriptionOrderSchema(
            season_id=season.id,
            items=[
                SubscriptionOrderItem(player_id=i["player_id"], plan_type=i["tier"]) for i in items
            ],
        )
        _, lines = build_subscription_order(order)
    except ValidationError as error:
        return str(error)
    return season, [
        {
            "player_id": player.id,
            "full_name": full_name(player.user),
            "tier": item["tier"],
            "kind": priced.kind,
            "amount_paise": priced.amount,
        }
        for item, (player, priced) in zip(items, lines, strict=True)
    ]


def place_order(
    ctx: ToolContext, season: Season, lines: list[dict[str, Any]], total: int
) -> ToolResult:
    items = [{"player_id": line["player_id"], "tier": line["tier"]} for line in lines]
    again = quote_items(items)
    if isinstance(again, str):
        return fail(again)
    now_total = sum(line["amount_paise"] for line in again[1])
    shape = [(line["player_id"], line["amount_paise"]) for line in lines]
    if shape != [(line["player_id"], line["amount_paise"]) for line in again[1]]:
        return fail(
            f"The price changed from {rupees(total)} to {rupees(now_total)}. Nothing was ordered.",
            hint="Quote again and ask the user before buying.",
        )
    body = {
        "season_id": season.id,
        "items": [{"player_id": i["player_id"], "plan_type": i["tier"]} for i in items],
    }
    response = call_api(ctx, "POST", "/api/transactions/razorpay", body=body)
    if not response.ok:
        return denied(response)
    order_id = response.data["order_id"]
    return ok(
        {
            "order_id": order_id,
            **money(response.data["amount"]),
            "pay_url": pay_link(order_id),
            "message": "Order created. Open pay_url to pay; membership starts once it is paid.",
        }
    )


@tool(
    "buy_membership",
    title="Buy memberships",
    description=(
        "Create a payment order for memberships, for the signed-in user, their wards or anyone "
        "else. Each item is {player_id, tier}; tiers come from get_membership_options. Several "
        "people can go in one order, but an upgrade has to be bought for one person alone. The "
        "user is asked to confirm the total first. Nothing is charged here: the result is an "
        "order_id and a pay_url the user opens to pay."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "player_id": {"type": "integer"},
                        "tier": {"type": "string", "minLength": 1, "maxLength": 50},
                    },
                    "required": ["player_id", "tier"],
                    "additionalProperties": False,
                },
                "maxItems": MAX_PLAYERS,
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    writes=True,
)
def buy_membership(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    quoted = quote_items(args["items"])
    if isinstance(quoted, str):
        return fail(quoted)
    season, lines = quoted
    total = sum(line["amount_paise"] for line in lines)
    people = ", ".join(
        f"{line['full_name']} ({line['tier']}, {rupees(line['amount_paise'])})" for line in lines
    )
    waiting = [
        line["full_name"]
        for line in lines
        if unpaid_membership(ctx.user, line["player_id"], season)
    ]
    note = (
        f"{', '.join(waiting)} already {'has' if len(waiting) == 1 else 'have'} a membership "
        "order waiting to be paid; paying both "
        "would pay twice. "
        if waiting
        else ""
    )
    return confirm_then(
        ctx,
        message=f"{note}Create a payment order of {rupees(total)} for {people}? You pay it afterwards.",
        binding={
            "season_id": season.id,
            "items": [{k: v for k, v in line.items() if k != "full_name"} for line in lines],
            "total_paise": total,
            "confirmation": args.get("confirmation", ""),
        },
        action=lambda: place_order(ctx, season, lines, total),
    )


def _order(row: dict[str, Any], mine: set[str]) -> dict[str, Any]:
    paid_up = row["status"] in RazorpayTransaction.SETTLED
    entry: dict[str, Any] = {
        "order_id": row["order_id"],
        **money(row["amount"]),
        "status": row["status"],
        "kind": row["type"],
        "players": row["players"],
        "paid_on": row["payment_date"],
    }
    if row["receipt_id"]:
        entry["receipt_id"] = row["receipt_id"]
        entry["receipt_url"] = receipt_link(row["receipt_id"])
    if not paid_up and row["status"] != "failed" and row["order_id"] in mine:
        entry["pay_url"] = pay_link(row["order_id"])
    return entry


@tool(
    "list_my_payments",
    title="My payments and receipts",
    description=(
        "The signed-in user's receipts (with a receipt_url), their online orders, and orders "
        "still unpaid with a pay_url to finish paying. Orders include ones others paid for the "
        "user or their wards. Pass kind to see only receipts, orders or unpaid."
    ),
    input_schema={
        "type": "object",
        "properties": {"kind": {"type": "string", "enum": KINDS}},
        "additionalProperties": False,
    },
)
def list_my_payments(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    kind = args.get("kind")
    result: dict[str, Any] = {}
    if kind in (None, "receipts"):
        response = call_api(ctx, "GET", "/api/receipts")
        if not response.ok:
            return denied(response)
        result["receipts"] = [
            {
                "receipt_id": r["id"],
                "number": r["number"],
                "kind": r["kind"],
                "date": r["date"],
                "summary": r["summary"],
                **money(r["total"], "total"),
                "original_receipt_id": r["original_id"],
                "receipt_url": receipt_link(r["id"]),
            }
            for r in response.data
        ]
    if kind in (None, "orders", "unpaid"):
        response = call_api(ctx, "GET", "/api/transactions/", query={"user_only": "true"})
        if not response.ok:
            return denied(response)
        rows = [r for r in response.data if r["type"] == "R"]
        mine = set(
            RazorpayTransaction.objects.filter(
                order_id__in=[r["order_id"] for r in rows], user=ctx.user
            ).values_list("order_id", flat=True)
        )
        orders = sorted((_order(r, mine) for r in rows), key=lambda o: not _open(o))
        if kind == "unpaid":
            orders = [o for o in orders if "pay_url" in o or _open(o)]
        result["orders"] = orders
    for key in ("receipts", "orders"):
        if key in result:
            result = cap(result, list_key=key, hint=HINT, truncated_key=f"{key}_truncated")
    return ok(result)


def _open(order: dict[str, Any]) -> bool:
    return order["status"] not in (*RazorpayTransaction.SETTLED, "failed")


@tool(
    "request_sponsorship",
    title="Ask for a sponsored membership",
    description=(
        "Ask Hub staff to approve the sponsored membership tier for one or more players this "
        "season, with a short reason. Staff review it; once approved, the tier shows up in "
        "get_membership_options. Only one waiting request per player and season."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "player_ids": {**PLAYER_IDS, "minItems": 1},
            "message": {"type": "string", "minLength": 1, "maxLength": MAX_MESSAGE},
        },
        "required": ["player_ids", "message"],
        "additionalProperties": False,
    },
    writes=True,
)
def request_sponsorship(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    ids = list(dict.fromkeys(args["player_ids"]))
    if not ids:
        return fail("player_ids: give at least one player")
    season = Season.current()
    if season is None:
        return fail("No season is running right now.")
    found = {p.id: p for p in Player.objects.filter(id__in=ids).select_related("user")}
    if missing := [i for i in ids if i not in found]:
        return fail(f"No players with player_id {missing}")
    names = ", ".join(full_name(found[i].user) for i in ids)

    def send() -> ToolResult:
        response = call_api(
            ctx,
            "POST",
            "/api/service-requests/",
            body={
                "type": "REQUEST_SPONSORED_SUBSCRIPTION",
                "message": args["message"],
                "service_player_ids": ids,
                "season_id": season.id,
            },
        )
        if not response.ok:
            return denied(response)
        return ok(
            {
                "request_id": response.data["id"],
                "status": response.data["status"],
                "players": names,
                "message": "Request sent. Staff will review it.",
            }
        )

    return confirm_then(
        ctx,
        message=(
            f"Ask Hub staff to sponsor the {season.name} membership for {names}, "
            f'saying: "{args["message"]}"?'
        ),
        binding={
            "player_ids": ids,
            "message": args["message"],
            "confirmation": args.get("confirmation", ""),
        },
        action=send,
    )
