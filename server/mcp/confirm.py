import hashlib
import json
import secrets
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils.timezone import now

from server.mcp.models import McpNonce
from server.mcp.registry import TOOLS, ToolContext, ToolResult, fail, ok, spend_email_budget

SALT = "mcp-confirm"
MAX_AGE = 600
HOW = (
    "Show this to the user. Call again with the same arguments "
    "and this confirmation only if they say yes."
)
CHANGED = "Something changed since you were asked, so check again.\n\n"
CLOSED = (
    "The question was closed without an answer. Ask the user in chat, and only call "
    "again with this confirmation if they say yes.\n\n"
)
DECLINED = {
    "decline": "Not done: you said no.",
    "cancel": "Not done: you closed the question.",
}


def _can_elicit(ctx: ToolContext) -> bool:
    capability = ctx.client_capabilities.get("elicitation")
    return ctx.modern and isinstance(capability, dict) and (not capability or "form" in capability)


def _digest(binding: dict[str, Any]) -> str:
    text = json.dumps(binding, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _verify(ctx: ToolContext, state: str, digest: str, mode: str) -> tuple[str | None, str]:
    """The nonce from a good state, or None with what is wrong with it.

    A state answered in the client's dialog is never accepted as a chat confirmation,
    and the other way round, so a model can't skip the dialog it was shown.
    """
    try:
        payload = signing.loads(state, salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired:
        return None, "This confirmation expired. Start again."
    except signing.BadSignature:
        return None, "This confirmation is not valid. Start again."
    if (
        payload.get("u") != ctx.user.pk
        or payload.get("t") != ctx.tool_name
        or payload.get("m", "chat") != mode
    ):
        return None, "This confirmation is for a different request. Start again."
    if payload.get("d") != digest:
        return None, CHANGED
    return str(payload["n"]), ""


def confirm_then(
    ctx: ToolContext,
    *,
    message: str,
    binding: dict[str, Any],
    action: Callable[[], ToolResult],
    emails: int = 1,
) -> ToolResult:
    arguments = {k: v for k, v in binding.items() if k != "confirmation"}
    digest = _digest(arguments)
    elicit = _can_elicit(ctx)
    responses = ctx.input_responses or {}
    if elicit and ctx.request_state and "confirm" in responses:
        state, mode, response = ctx.request_state, "dialog", responses["confirm"]
    elif binding.get("confirmation"):
        state, mode = binding["confirmation"], "chat"
        response = {"action": "accept", "content": {"confirm": True}}
    else:
        return _ask(ctx, message, digest, elicit)

    nonce, problem = _verify(ctx, state, digest, mode)
    if problem == CHANGED:
        return _ask(ctx, CHANGED + message, digest, elicit)
    if nonce is None:
        return fail(problem)
    verdict = response.get("action") if isinstance(response, dict) else None
    if verdict == "cancel":
        return _ask(ctx, CLOSED + message, digest, elicit=False)
    if verdict != "accept":
        return ok({"done": False, "message": DECLINED.get(str(verdict), DECLINED["cancel"])})
    content = response.get("content")
    if not isinstance(content, dict) or content.get("confirm") is not True:
        return ok({"done": False, "message": DECLINED["decline"]})

    try:
        with transaction.atomic():
            McpNonce.objects.create(key=nonce, expires_at=now() + timedelta(seconds=MAX_AGE * 2))
    except IntegrityError:
        return fail("This confirmation was already used. Start again.")
    tool = TOOLS.get(ctx.tool_name)
    if tool and tool.emails and emails and (limited := spend_email_budget(ctx, emails)):
        McpNonce.objects.filter(key=nonce).delete()
        return limited
    with transaction.atomic():
        result = action()
        if result.is_error:
            transaction.set_rollback(True)
    if result.is_error:
        McpNonce.objects.filter(key=nonce).delete()
    return result


def _ask(ctx: ToolContext, message: str, digest: str, elicit: bool) -> ToolResult:
    mode = "dialog" if elicit else "chat"
    state = signing.dumps(
        {"u": ctx.user.pk, "t": ctx.tool_name, "d": digest, "n": secrets.token_hex(16), "m": mode},
        salt=SALT,
    )
    if not elicit:
        return ok(
            {
                "done": False,
                "needs_confirmation": message,
                "confirmation": state,
                "how": HOW,
            }
        )
    schema = {
        "type": "object",
        "properties": {"confirm": {"type": "boolean", "title": "Yes, do this"}},
        "required": ["confirm"],
    }
    params = {"mode": "form", "message": message, "requestedSchema": schema}
    return ToolResult(
        None,
        input_required={
            "inputRequests": {"confirm": {"method": "elicitation/create", "params": params}},
            "requestState": state,
        },
    )
