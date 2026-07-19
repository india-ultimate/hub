"""PII masking gateway for tournament agent model traffic."""

from __future__ import annotations

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Match common phone forms but not ISO dates (YYYY-MM-DD).
PHONE_RE = re.compile(
    r"(?<!\d)("
    r"\+\d{1,3}[\s\-]?(?:\d[\s\-]?){8,14}\d"  # +91 98765 43210
    r"|(?:\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4})"  # (555) 123-4567 / 555-123-4567
    r"|(?<![\d-])\d{10,15}(?![\d-])"  # 10+ continuous digits, not date fragments
    r")(?!\d)"
)

# Keys that must never appear in model-bound tool payloads.
FORBIDDEN_KEYS = frozenset(
    {
        "email",
        "phone",
        "phone_number",
        "mobile",
        "membership_number",
        "first_name",
        "last_name",
        "full_name",
        "guardian_email",
        "player_id",
        "user_id",
        "volunteer",
        "volunteers",
        "registrations",
        "roster",
        "players",
        "spirit_score",
        "mvp",
        "msp",
    }
)


def scrub_user_text(text: str) -> str:
    """Strip emails/phones from freeform user input before sending to the model."""
    scrubbed = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    scrubbed = PHONE_RE.sub("[REDACTED_PHONE]", scrubbed)
    return scrubbed


def contains_forbidden_keys(obj: Any, path: str = "") -> list[str]:
    """Return list of forbidden key paths found in nested JSON."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            full = f"{path}.{key}" if path else str(key)
            if key_l in FORBIDDEN_KEYS:
                found.append(full)
            found.extend(contains_forbidden_keys(value, full))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(contains_forbidden_keys(item, f"{path}[{i}]"))
    return found


def assert_safe_tool_payload(payload: Any) -> None:
    bad = contains_forbidden_keys(payload)
    if bad:
        raise ValueError(f"PII/forbidden keys in tool payload: {', '.join(bad)}")


def scrub_json_strings(obj: Any) -> Any:
    """Recursively scrub emails/phones inside string values of JSON-like data."""
    if isinstance(obj, str):
        return scrub_user_text(obj)
    if isinstance(obj, dict):
        return {k: scrub_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_json_strings(v) for v in obj]
    return obj


class SessionPseudonymMap:
    """Optional stable team pseudonyms for a session (Team:42 -> Team_T7)."""

    def __init__(self) -> None:
        self._team: dict[int, str] = {}
        self._next = 1

    def team_token(self, team_id: int) -> str:
        if team_id not in self._team:
            self._team[team_id] = f"Team_T{self._next}"
            self._next += 1
        return self._team[team_id]

    def mask_team_name(self, team_id: int | None, name: str | None, *, use_pseudonyms: bool) -> str:
        if team_id is None:
            return name or ""
        if use_pseudonyms:
            return self.team_token(team_id)
        return name or f"Team {team_id}"
