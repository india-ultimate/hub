"""Contact details never reach an AI agent: not the user's own, not anyone else's, even
where the user's own Hub login could see them. People are named and given by id.

Every tool result goes through `scrub` on its way out, so a field a tool forgot, an
API response passed through, or an address typed into a ticket is still held back.
"""

import re
from typing import Any

# A field holding contact details or a birth date: email, guardian_phone, dateOfBirth...
FIELD = re.compile(
    r"(?:^|_)(?:e?mails?|e?mail_address(?:es)?|phones?|phone_numbers?|mobile(?:_number)?"
    r"|whatsapp(?:_number)?|tel|telephone|msisdn|date_of_birth|dob|birth_?date|birthday|born)$"
)
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
URL = r"https?://\S+"
# Starts only where a word starts, so a long run of letters is read once, not once per letter.
EMAIL = r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]+(?:\.[\w-]+)+"
EDGE, END = r"(?<![\w+/=:.-])", r"(?![\w/=:-])"
# An Indian mobile however it's written (+91 98765 43210, (+91) 98 7654-3210, 919876543210),
# a landline with its STD code (022 2345 6789), or any number with a country code.
PHONE = (
    rf"{EDGE}(?:\(?\+?91\)?[\s.-]?|0)?\(?[6-9](?:[\s.()-]?\d){{9}}{END}"
    rf"|{EDGE}0\d{{2,4}}[\s-]?\d{{3,4}}[\s-]?\d{{4}}{END}"
    r"|(?<![\w+])\+\d{1,3}[\s-]?\d[\d\s-]{6,13}\d(?!\w)"
)
MONTH = r"[A-Za-z]{3,9}"
DAY = r"\d{1,2}(?:st|nd|rd|th)?"
DATE = (
    rf"\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"
    rf"|{DAY}\s+{MONTH},?\s+\d{{4}}|{MONTH}\s+{DAY},?\s+\d{{4}}"
)
BIRTH = (
    rf"\b(?:dob|d\.o\.b\.?|date of birth|birth ?date|birthday|born(?: on)?)\s*[:-]?\s*(?:{DATE})"
)
TEXT = re.compile(f"({URL})|({EMAIL})|({BIRTH})|({PHONE})", re.IGNORECASE)
# India Ultimate's own published address, which the waivers name: not a person's.
PUBLIC_EMAILS = {"operations@indiaultimate.org"}
EMAIL_HIDDEN = "[email hidden]"
PHONE_HIDDEN = "[phone hidden]"
BIRTH_HIDDEN = "[date of birth hidden]"


def is_private(field: str) -> bool:
    return bool(FIELD.search(CAMEL.sub("_", field).lower()))


def _hide(match: re.Match[str]) -> str:
    url, email, birth, _ = match.groups()
    if url:
        return EMAIL_HIDDEN if re.search(EMAIL, url) else url
    if email:
        return email if email.lower() in PUBLIC_EMAILS else EMAIL_HIDDEN
    return BIRTH_HIDDEN if birth else PHONE_HIDDEN


def scrub(value: Any) -> Any:
    """`value` without private fields, and with emails, phone numbers and birth dates in
    its text hidden. Yes/no flags keep their names (phone: true)."""
    if isinstance(value, dict):
        return {
            key: scrub(item)
            for key, item in value.items()
            if not (is_private(str(key)) and not isinstance(item, bool))
        }
    if isinstance(value, (list, tuple)):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return TEXT.sub(_hide, value)
    return value
