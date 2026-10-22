import datetime
import os
import re
from collections.abc import Callable
from typing import Any, TypeVar

from django.conf import settings
from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Min
from django.utils.timezone import now

from server.announcements.access import can_manage, can_post
from server.announcements.models import Announcement
from server.core.models import Guardianship, Player, Team, User
from server.mcp.registry import Audience, ToolContext, ToolResult, fail, ok, tool
from server.payment_account.models import viewable_by
from server.series.models import Series
from server.series.utils import may_answer_for
from server.subscription import eligibility
from server.subscription.api import may_see
from server.subscription.models import Subscription
from server.task.manager import TaskManager
from server.task.models import Task
from server.ticket.access import can_handle
from server.ticket.models import Ticket
from server.tournament.models import Event, Match, Tournament
from server.tournament.utils import can_manage_tournament, user_tournament_teams
from server.transaction.models import RazorpayTransaction
from server.utils import today

FLY = ("FLY_APP_NAME", "FLY_REGION", "FLY_IMAGE_REF", "FLY_MACHINE_VERSION")
FAILURES = 10
ERROR_CHARS = 200
EMAIL = re.compile(r"\S+@\S+")
PHONE = re.compile(r"\+?\d[\d\s-]{7,}\d")
UNAPPLIED_SHOWN = 20
Answer = tuple[bool, str, str]


def _migrations() -> dict[str, Any]:
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return {"unapplied": [f"{m.app_label}.{m.name}" for m, _ in plan][:UNAPPLIED_SHOWN]}


def _first_line(error: str) -> str:
    line = error.strip().split("\n")[0]
    return PHONE.sub("[phone]", EMAIL.sub("[email]", line))[:ERROR_CHARS]


def _tasks() -> dict[str, Any]:
    failures = Task.objects.filter(failed_at__isnull=False).order_by("-failed_at")[:FAILURES]
    return {
        "stats": TaskManager.get_task_stats(),
        "recent_failures": [
            {
                "task_id": t.pk,
                "type": t.type,
                "error": _first_line(t.error),
                "failed_at": t.failed_at.isoformat() if t.failed_at else None,
            }
            for t in failures
        ],
    }


def _cache() -> dict[str, Any]:
    backend = settings.CACHES["default"]["BACKEND"]
    if isinstance(caches["default"], DummyCache):
        return {"backend": backend, "reachable": False, "note": "No cache is configured."}
    try:
        cache.get("mcp:ping")
    except Exception:
        return {"backend": backend, "reachable": False}
    return {"backend": backend, "reachable": True}


def _flags() -> dict[str, bool]:
    return {
        "tournament_agent_enabled": bool(settings.TOURNAMENT_AGENT_ENABLED),
        "mcp_enabled": bool(settings.MCP_ENABLED),
        "debug": bool(settings.DEBUG),
        "redis_configured": bool(os.environ.get("REDIS_HOST")),
        "sentry_configured": bool(os.environ.get("SENTRY_DSN")),
        "groq_api_key_set": bool(settings.GROQ_API_KEY),
        "opencode_go_api_key_set": bool(settings.OPENCODE_GO_API_KEY),
    }


def _cron() -> dict[str, Any]:
    oldest = Task.objects.filter(completed_at__isnull=False).aggregate(oldest=Min("completed_at"))
    stale = now() - datetime.timedelta(days=1)
    return {
        "expired_active_subscriptions": Subscription.objects.filter(
            is_active=True, end_date__lt=today()
        ).count(),
        "unsettled_orders_over_a_day_old": RazorpayTransaction.objects.exclude(
            status__in=RazorpayTransaction.SETTLED
        )
        .filter(payment_date__lt=stale)
        .count(),
        "oldest_finished_task_at": oldest["oldest"].isoformat() if oldest["oldest"] else None,
    }


@tool(
    "get_system_status",
    title="System status",
    description=(
        "Read-only health of the Hub: Fly app and region, unapplied migrations, task queue and "
        "the last failures (error text cut to its first line, with emails and phones masked), cache, feature flags (secrets only as set or not), and signs that "
        "the nightly jobs ran."
    ),
    input_schema={"type": "object", "additionalProperties": False},
    audience=Audience.DEVELOPER,
)
def get_system_status(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    return ok(
        {
            "fly": {name: os.environ.get(name) for name in FLY},
            "migrations": _migrations(),
            "tasks": _tasks(),
            "cache": _cache(),
            "flags": _flags(),
            "cron": _cron(),
        }
    )


def _need(ref: str | None, what: str) -> str:
    if not ref:
        raise LookupError(f"This check needs object_ref: {what}.")
    return ref


T = TypeVar("T")


def _found(row: T | None, what: str) -> T:
    if row is None:
        raise LookupError(f"No {what} found.")
    return row


def _player(ref: str | None) -> Player:
    ref = _need(ref, "a player_id")
    return _found(Player.objects.filter(pk=ref).first() if ref.isdigit() else None, "player")


def _tournament(ref: str | None) -> Tournament:
    ref = _need(ref, "an event_slug")
    return _found(Tournament.objects.filter(event__slug=ref).first(), "tournament")


def _see_player(user: User, ref: str | None) -> Answer:
    player = _player(ref)
    if player.user_id == user.pk:
        return True, "self", "It is their own profile."
    if Guardianship.objects.filter(player=player, user_id=user.pk).exists():
        return True, "guardian", "They are this player's guardian."
    allowed = may_see(user, player)
    return (
        allowed,
        "staff" if allowed else "none",
        ("Staff can see every player." if allowed else "Not themselves, a guardian or staff."),
    )


def _answer_invitation_for(user: User, ref: str | None) -> Answer:
    player = _player(ref)
    allowed = may_answer_for(user, player)
    return (
        allowed,
        "self_or_guardian",
        (
            "They are the player or the player's guardian."
            if allowed
            else "Only the player or their guardian answers; staff cannot."
        ),
    )


def _manage_tournament(user: User, ref: str | None) -> Answer:
    tournament = _tournament(ref)
    allowed = can_manage_tournament(user, tournament)
    if not allowed:
        return False, "staff_or_director", "Not staff and not a director of this tournament."
    return (
        True,
        "staff" if user.is_staff else "director",
        ("Staff manage every tournament." if user.is_staff else "They direct this tournament."),
    )


def _submit_scores(user: User, ref: str | None) -> Answer:
    ref = _need(ref, "a match_id")
    match = _found(
        (
            Match.objects.select_related("tournament__event").filter(pk=ref).first()
            if ref.isdigit()
            else None
        ),
        "match",
    )
    _, admin_team_ids = user_tournament_teams(match.tournament, user)
    allowed = bool({match.team_1_id, match.team_2_id} & admin_team_ids)
    return (
        allowed,
        "team_captain_or_admin",
        (
            "They are a captain or admin of a team in this match."
            if allowed
            else "Only a captain or admin of a team in the match submits its score; staff do not."
        ),
    )


def _handle_ticket(user: User, ref: str | None) -> Answer:
    ref = _need(ref, "a ticket_id")
    ticket = _found(Ticket.objects.filter(pk=ref).first() if ref.isdigit() else None, "ticket")
    allowed = can_handle(user, ticket)
    return (
        allowed,
        "staff_or_routed_committee",
        (
            "Staff, or on a committee this category routes to."
            if allowed
            else "Not staff and not on a committee this category routes to."
        ),
    )


def _post_announcements(user: User, ref: str | None) -> Answer:
    if ref:
        post = _found(Announcement.objects.filter(slug=ref).first(), "announcement")
        allowed = can_manage(user, post)
        return (
            allowed,
            "can_manage",
            (
                "Staff, or the author who can still post."
                if allowed
                else "Only staff or the author (while they can post) manage a post."
            ),
        )
    allowed = can_post(user)
    return (
        allowed,
        "can_post",
        (
            "Staff, or a current role that can post announcements."
            if allowed
            else "Not staff and no current role that can post."
        ),
    )


def _view_payment_account(user: User, ref: str | None) -> Answer:
    accounts = viewable_by(user)
    allowed = (accounts.filter(slug=ref) if ref else accounts).exists()
    return (
        allowed,
        "staff_or_viewer",
        (
            "Staff, or made a viewer of the account."
            if allowed
            else "Not staff and not a viewer of the account."
        ),
    )


def _team_admin(user: User, ref: str | None) -> Answer:
    if ref:
        team = _found(Team.objects.filter(slug=ref).first(), "team")
        allowed = team.admins.filter(pk=user.pk).exists()
    else:
        allowed = user.admin_teams.exists()
    return allowed, "team_admin", "They administer it." if allowed else "They do not administer it."


def _can_play(user: User, ref: str | None) -> Answer:
    ref = _need(ref, "an event_slug or series_slug")
    player = Player.objects.filter(user=user).first()
    if player is None:
        return False, "player_profile", "They have no player profile yet."
    targets = (Event.objects.filter(slug=ref).first(), Series.objects.filter(slug=ref).first())
    for target in targets:
        if target is not None:
            problem = eligibility.check(player, target, is_playing=True)
            break
    else:
        raise LookupError("No event or series found.")
    if problem is None:
        return True, "eligibility", "Subscription, waiver and code of conduct are in order."
    return False, "eligibility", problem["message"]


CHECKS: dict[str, Callable[[User, str | None], Answer]] = {
    "see_player": _see_player,
    "answer_invitation_for": _answer_invitation_for,
    "manage_tournament": _manage_tournament,
    "submit_scores": _submit_scores,
    "handle_ticket": _handle_ticket,
    "post_announcements": _post_announcements,
    "view_payment_account": _view_payment_account,
    "team_admin": _team_admin,
    "can_play": _can_play,
}


@tool(
    "explain_access",
    title="Explain an access decision",
    description=(
        "Say whether a person is allowed something and why, by running Hub's own check. "
        "Name the person with user_id or email (default: you). object_ref is what the check is "
        "about: a player_id (see_player, answer_invitation_for), an event_slug "
        "(manage_tournament, can_play; or a series_slug), a match_id (submit_scores), a "
        "ticket_id (handle_ticket), an announcement slug (post_announcements, optional), a "
        "payment account slug (view_payment_account, optional) or a team_slug (team_admin, "
        "optional)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "check": {"type": "string", "enum": sorted(CHECKS)},
            "user_id": {"type": "integer", "minimum": 1},
            "email": {"type": "string", "maxLength": 254},
            "object_ref": {"type": "string", "maxLength": 100},
        },
        "required": ["check"],
        "additionalProperties": False,
    },
    audience=Audience.DEVELOPER,
)
def explain_access(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    if "user_id" in args:
        subject = User.objects.filter(pk=args["user_id"]).first()
    elif "email" in args:
        subject = User.objects.filter(username__iexact=args["email"].strip()).first()
    else:
        subject = ctx.user
    if subject is None:
        return fail("No Hub user matches that user_id or email.")
    try:
        allowed, rule, because = CHECKS[args["check"]](subject, args.get("object_ref"))
    except LookupError as error:
        return fail(str(error))
    return ok(
        {
            "check": args["check"],
            "user_id": subject.pk,
            "allowed": allowed,
            "rule": rule,
            "because": because,
        }
    )
