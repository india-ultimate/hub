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

# Identity, not identifiers: an id may always cross the boundary, a person's name
# or contact detail never may. These keys must not appear in anything a tool
# returns to the model.
#
# `comments` is listed because spirit comments are free text people write names
# into. It stays accepted as a tool *argument* — this list only guards results,
# since proposal payloads are stored, never replayed into model context.
FORBIDDEN_KEYS = frozenset(
    {
        # contact
        "email",
        "guardian_email",
        "phone",
        "phone_number",
        "mobile",
        # identity
        "first_name",
        "last_name",
        "full_name",
        "username",
        "player_name",
        "person_name",
        "mvp_name",
        "msp_name",
        # sensitive attributes and free text
        "membership_number",
        "date_of_birth",
        "dob",
        "gender",
        "other_gender",
        "match_up",  # gender-matching category on Player
        "comments",
    }
)

# Keys that carry a person. Their values must be bare ids, so a nested object
# smuggling a name in fails loudly instead of relying on someone remembering to
# flatten it.
ID_ONLY_KEYS = frozenset(
    {
        "mvp",
        "msp",
        "mvp_id",
        "msp_id",
        "mvp_player_id",
        "msp_player_id",
        "player_id",
        "entered_by",
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


def non_id_person_values(obj: Any, path: str = "") -> list[str]:
    """Return paths where a person-bearing key holds something other than an id."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            full = f"{path}.{key}" if path else str(key)
            # A bool, a nested object, or a string that is not digits — all of them
            # mean this person-bearing key is carrying more than an id.
            if (
                str(key).lower() in ID_ONLY_KEYS
                and value is not None
                and (
                    isinstance(value, bool)
                    or not isinstance(value, int | str)
                    or (isinstance(value, str) and not value.isdigit())
                )
            ):
                found.append(full)
            found.extend(non_id_person_values(value, full))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(non_id_person_values(item, f"{path}[{i}]"))
    return found


def assert_safe_tool_payload(payload: Any) -> None:
    bad = contains_forbidden_keys(payload)
    if bad:
        raise ValueError(f"PII/forbidden keys in tool payload: {', '.join(bad)}")
    not_ids = non_id_person_values(payload)
    if not_ids:
        raise ValueError(f"Person fields must be ids, not objects/names: {', '.join(not_ids)}")


def scrub_json_strings(obj: Any) -> Any:
    """Recursively scrub emails/phones inside string values of JSON-like data."""
    if isinstance(obj, str):
        return scrub_user_text(obj)
    if isinstance(obj, dict):
        return {k: scrub_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_json_strings(v) for v in obj]
    return obj
