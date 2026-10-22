from collections import Counter
from typing import Any

from django.db.models import Count, Sum

from server.core.models import Player, StatesUTs
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.mcp.shape import money
from server.mcp.tools.staff_members import find_season, previous_season, season_slug
from server.season.models import Season
from server.subscription.models import Subscription
from server.tournament.models import Event, Registration
from server.transaction.models import RazorpayRefund, RazorpayTransaction
from server.utils import today

SMALL = 5
TOP = 20
GROUPS = ["tier", "state", "gender", "age_band"]
BANDS = [(18, "Under 18"), (25, "18 to 24"), (35, "25 to 34")]
SHOWN = "<5"


def _band(age: float) -> str:
    return next((label for limit, label in BANDS if age < limit), "35 and over")


def _hide(count: int) -> int | str:
    return SHOWN if count < SMALL else count


def _groups(counts: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"group": name, "count": _hide(count)}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _members(season: Season, group_by: str) -> dict[str, Any]:
    subs = Subscription.objects.for_season(season).filter(is_active=True)
    states = dict(StatesUTs.choices)
    genders = dict(Player.GenderTypes.choices)
    counts: Counter[str] = Counter()
    for sub in subs.select_related("player", "plan__type"):
        player = sub.player
        if group_by == "tier":
            name = sub.plan.type.name if sub.plan else "Unknown"
        elif group_by == "state":
            name = str(states.get(player.state_ut or "", "Not given"))
        elif group_by == "gender":
            name = str(genders.get(player.gender, "Not given"))
        else:
            name = _band(player.age_on(min(today(), season.end_date)))
        counts[name] += 1
    return {
        "groups": _groups(counts),
        "definition": (
            f"Players with an active, unrefunded subscription for {season.name}, "
            f"grouped by {group_by.replace('_', ' ')}."
        ),
        "coverage": "Every active member; age bands use date of birth on today's date.",
    }


def _renewals(season: Season) -> dict[str, Any]:
    last = previous_season(season)
    here = set(Subscription.objects.for_season(season).values_list("player_id", flat=True))
    before = set(Subscription.objects.for_season(last).values_list("player_id", flat=True))
    counts = Counter(
        {
            "Renewed (members last season and this)": len(here & before),
            "Not renewed yet (members last season only)": len(before - here),
            "New (members this season only)": len(here - before),
        }
    )
    return {
        "groups": _groups(counts),
        "definition": (
            f"{season.name} against {last.name if last else 'no earlier season'}. "
            "A member is anyone with an unrefunded subscription, active or not."
        ),
        "coverage": "Every subscription in both seasons.",
    }


def _orders(season: Season) -> Any:
    return RazorpayTransaction.objects.filter(
        payment_date__date__gte=season.start_date, payment_date__date__lte=season.end_date
    )


def _revenue(season: Season) -> dict[str, Any]:
    paid = _orders(season).filter(status__in=RazorpayTransaction.SETTLED)
    refunded = {
        row["transaction__type"]: row["total"]
        for row in RazorpayRefund.objects.filter(
            transaction__in=paid, status=RazorpayRefund.Status.PROCESSED
        )
        .values("transaction__type")
        .annotate(total=Sum("amount"))
    }
    groups = []
    for row in (
        paid.values("type").annotate(orders=Count("pk"), gross=Sum("amount")).order_by("type")
    ):
        net = row["gross"] - refunded.get(row["type"], 0)
        small = row["orders"] < SMALL
        groups.append(
            {
                "group": str(RazorpayTransaction.TransactionTypeChoices(row["type"]).label),
                "orders": _hide(row["orders"]),
                **({"amount_paise": None, "amount": SHOWN} if small else money(net)),
            }
        )
    return {
        "groups": groups,
        "definition": (
            f"Paid orders created during {season.name}, by what they paid for, "
            "less refunds Razorpay has processed."
        ),
        "coverage": "Razorpay orders only; manual and PhonePe payments are not counted.",
    }


def _funnel(season: Season) -> dict[str, Any]:
    labels = dict(RazorpayTransaction.TransactionStatusChoices.choices)
    counts = Counter(
        {
            str(labels.get(row["status"], row["status"])): row["n"]
            for row in _orders(season).values("status").annotate(n=Count("pk"))
        }
    )
    return {
        "groups": _groups(counts),
        "definition": (
            f"Checkouts started during {season.name} by where they ended: Pending means never paid."
        ),
        "coverage": "Razorpay orders only.",
    }


def _registrations(season: Season) -> dict[str, Any]:
    rows = (
        Registration.objects.filter(
            is_playing=True,
            event__start_date__gte=season.start_date,
            event__start_date__lte=season.end_date,
        )
        .values("event")
        .annotate(n=Count("pk"))
        .order_by("-n", "event")[:TOP]
    )
    events = {e.pk: e for e in Event.objects.filter(pk__in=[r["event"] for r in rows])}
    return {
        "groups": [
            {
                "group": events[r["event"]].title,
                "event_slug": events[r["event"]].slug,
                "count": _hide(r["n"]),
            }
            for r in rows
        ],
        "definition": (
            f"Players on a roster, for tournaments starting in {season.name}; the {TOP} biggest."
        ),
        "coverage": "Rostered players only, not teams still paying.",
    }


@tool(
    "get_metrics",
    title="Hub metrics",
    audience=Audience.STAFF,
    description=(
        "A fixed set of counts: members (group_by tier, state, gender or age_band), renewals, "
        "revenue by type, checkout_funnel, registrations by event. Counts under 5 show as "
        "'<5'. Every answer says how it is defined and what it covers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["members", "renewals", "revenue", "checkout_funnel", "registrations"],
            },
            "season_slug": {"type": "string", "minLength": 1, "maxLength": 100},
            "group_by": {"type": "string", "enum": GROUPS},
        },
        "required": ["metric"],
        "additionalProperties": False,
    },
)
def get_metrics(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    season = find_season(args.get("season_slug"))
    if season is None:
        return fail("No such season", hint="Use a slug like season-2026-2027")
    metric = args["metric"]
    answers = {
        "members": lambda: _members(season, args.get("group_by", "tier")),
        "renewals": lambda: _renewals(season),
        "revenue": lambda: _revenue(season),
        "checkout_funnel": lambda: _funnel(season),
        "registrations": lambda: _registrations(season),
    }
    return ok({"metric": metric, "season_slug": season_slug(season), **answers[metric]()})
