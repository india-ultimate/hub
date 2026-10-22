import json
import re
from typing import Any

from server.mcp.registry import ToolResult, fail
from server.receipts.money import rupees

SLUG = re.compile(r"[A-Za-z0-9_-]{1,255}")
SLUG_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 255}


def money(paise: int | None, name: str = "amount") -> dict[str, Any]:
    return {f"{name}_paise": paise, name: None if paise is None else rupees(paise)}


def slug_problem(**slugs: str | None) -> ToolResult | None:
    for name, value in slugs.items():
        if value is not None and not SLUG.fullmatch(value):
            return fail(f"{name}: use a slug such as nationals-2026 (letters, digits, - and _)")
    return None


def full_name(who: Any) -> str:
    who = getattr(who, "user", who)
    first, last = (
        (who["first_name"], who["last_name"])
        if isinstance(who, dict)
        else (who.first_name, who.last_name)
    )
    return f"{first} {last}".strip()


def cap(
    data: dict[str, Any],
    *,
    list_key: str,
    limit_chars: int = 30000,
    hint: str,
    truncated_key: str = "truncated",
) -> dict[str, Any]:
    """Trim data[list_key] until the JSON fits, and say how much was cut."""
    items = data[list_key]

    def size(count: int) -> int:
        # the text copy is the JSON escaped again, so measure that one
        return len(json.dumps(json.dumps({**data, list_key: items[:count]})))

    if size(len(items)) <= limit_chars:
        return data
    low, high = 0, len(items)
    while low < high:
        middle = (low + high + 1) // 2
        if size(middle) + 100 <= limit_chars:
            low = middle
        else:
            high = middle - 1
    return {
        **data,
        list_key: items[:low],
        truncated_key: {"shown": low, "total": len(items), "hint": hint},
    }


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "…"
