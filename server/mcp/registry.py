import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from django.utils.timezone import now

from server.announcements.access import can_post
from server.cache.store import safe
from server.committee.routing import committees_of
from server.core.models import User
from server.mcp.auth import TokenInfo
from server.payment_account.models import viewable_by
from server.tournament.models import Registration, UCRegistration
from server.tournament.utils import (
    ROLES_ELIGIBLE_TO_SUBMIT_SCORES,
    can_access_tournament_agent,
)

NAME = re.compile(r"[a-z0-9_]{1,64}")
JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


class Audience(StrEnum):
    EVERYONE = "everyone"
    TEAM_ADMIN = "team_admin"
    STAFF = "staff"
    CAPTAIN = "captain"
    HANDLER = "handler"
    POSTER = "poster"
    DIRECTOR = "director"
    ACCOUNT_VIEWER = "account_viewer"
    DEVELOPER = "developer"


def _is_captain(user: User) -> bool:
    if user.admin_teams.exists():
        return True
    if (
        Registration.objects.filter(player__user=user)
        .exclude(role=Registration.Role.DEFAULT)
        .exists()
    ):
        return True
    person_id = getattr(getattr(user, "player_profile", None), "ultimate_central_id", None)
    return person_id is not None and any(
        set(roles) & set(ROLES_ELIGIBLE_TO_SUBMIT_SCORES)
        for roles in UCRegistration.objects.filter(person_id=person_id).values_list(
            "roles", flat=True
        )
    )


CHECKS: dict[Audience, Callable[[User], bool]] = {
    Audience.EVERYONE: lambda user: True,
    Audience.TEAM_ADMIN: lambda user: user.admin_teams.exists(),
    Audience.STAFF: lambda user: user.is_staff,
    Audience.CAPTAIN: _is_captain,
    Audience.HANDLER: lambda user: user.is_staff or committees_of(user).exists(),
    Audience.POSTER: can_post,
    Audience.DIRECTOR: lambda user: (
        settings.TOURNAMENT_AGENT_ENABLED and can_access_tournament_agent(user)
    ),
    Audience.ACCOUNT_VIEWER: lambda user: viewable_by(user).exists(),
    Audience.DEVELOPER: lambda user: user.is_superuser,
}


def roles_of(user: User) -> set[Audience]:
    return {audience for audience, check in CHECKS.items() if check(user)}


@dataclass
class ToolContext:
    user: User
    token: TokenInfo
    modern: bool
    client_capabilities: dict[str, Any]
    input_responses: dict[str, Any] | None
    request_state: str | None
    tool_name: str
    outer: HttpRequest
    audit: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    data: Any
    is_error: bool = False
    input_required: dict[str, Any] | None = None


EMAIL_RATE_LIMIT = 30
CONFIRMATION = (
    "Leave out on the first call. Only after the user says yes, "
    "pass back the confirmation from the previous result."
)


def over_limit(key: str, ttl: int, limit: int, delta: int = 1) -> bool:
    def count() -> bool:
        cache.add(key, 0, ttl)
        try:
            return bool(cache.incr(key, delta) > limit)
        except ValueError:
            return False

    return safe(count, False)


def _email_key(ctx: ToolContext) -> str:
    return f"mcp-email:{ctx.user.pk}:{int(now().timestamp() // 3600)}"


def email_budget_left(ctx: ToolContext) -> bool:
    """Whether the user may still send an email this hour, without counting one."""
    return safe(lambda: int(cache.get(_email_key(ctx), 0)) < EMAIL_RATE_LIMIT, True)


def spend_email_budget(ctx: ToolContext, sends: int = 1) -> ToolResult | None:
    """Counts one email send against the user's hourly limit; the failure to return when over.

    `confirm_then` calls this before it runs the action of an `emails=True` tool. A tool
    that emails without a confirmation checks `email_budget_left` first and calls this
    once the email is sent.
    """
    if over_limit(_email_key(ctx), 3600, EMAIL_RATE_LIMIT, sends):
        return fail("You've sent a lot of emails through Hub this hour. Try again later.")
    return None


def ok(data: Any) -> ToolResult:
    return ToolResult(data)


def fail(message: str, **extra: Any) -> ToolResult:
    return ToolResult({"message": message, **extra}, is_error=True)


Handler = Callable[[ToolContext, dict[str, Any]], ToolResult]


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    audience: Audience
    writes: bool
    destructive: bool
    emails: bool
    handler: Handler = field(repr=False)

    def descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "title": self.title,
                "readOnlyHint": not self.writes,
                "destructiveHint": self.destructive,
                "openWorldHint": False,
            },
        }

    def visible_to(self, user: User, roles: set[Audience] | None = None) -> bool:
        if roles is not None:
            return self.audience in roles
        return CHECKS[self.audience](user)


TOOLS: dict[str, Tool] = {}


def tool(
    name: str,
    *,
    title: str,
    description: str,
    input_schema: dict[str, Any],
    audience: Audience = Audience.EVERYONE,
    writes: bool = False,
    destructive: bool = False,
    emails: bool = False,
) -> Callable[[Handler], Handler]:
    if not NAME.fullmatch(name):
        raise ValueError(f"Bad tool name {name!r}")

    schema = input_schema
    if writes:
        properties = {
            **schema.get("properties", {}),
            "confirmation": {"type": "string", "description": CONFIRMATION},
        }
        schema = {**schema, "properties": properties}

    def register(handler: Handler) -> Handler:
        TOOLS[name] = Tool(
            name, title, description, schema, audience, writes, destructive, emails, handler
        )
        return handler

    return register


def tools_for(user: User) -> list[Tool]:
    roles = roles_of(user)
    return sorted((t for t in TOOLS.values() if t.visible_to(user, roles)), key=lambda t: t.name)


def validate(value: Any, schema: dict[str, Any], path: str = "arguments") -> str | None:
    """The first problem with value, naming its field, or None."""
    kind = schema.get("type")
    if kind:
        is_number = kind in ("integer", "number")
        if not isinstance(value, JSON_TYPES[kind]) or (is_number and isinstance(value, bool)):
            return f"{path}: expected {kind}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{path}: must be one of {', '.join(map(str, schema['enum']))}"
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            return f"{path}: must have at least {schema['minLength']} characters"
        if len(value) > schema.get("maxLength", len(value)):
            return f"{path}: must have at most {schema['maxLength']} characters"
        if schema.get("format") == "date":
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                return f"{path}: expected a date like 2026-09-01"
    if isinstance(value, int | float) and value < schema.get("minimum", value):
        return f"{path}: must be at least {schema['minimum']}"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                return f"{path}.{key}: required"
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key not in properties:
                if schema.get("additionalProperties") is False:
                    return f"{path}.{key}: unexpected argument"
            elif error := validate(item, properties[key], f"{path}.{key}"):
                return error
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            if error := validate(item, schema["items"], f"{path}[{index}]"):
                return error
    return None
