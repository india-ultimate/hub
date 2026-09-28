"""Dates and amounts as a receipt prints them."""

import datetime
from zoneinfo import ZoneInfo

from num2words import num2words

INDIA = ZoneInfo("Asia/Kolkata")
APRIL = 4
LAKH_GROUP = 2  # digits per group above the thousands


def india_date(moment: datetime.datetime) -> datetime.date:
    """The calendar date in India, where the federation keeps its books."""
    return moment.astimezone(INDIA).date()


def financial_year(day: datetime.date) -> str:
    """India's April-to-March year, e.g. 2026-27."""
    start = day.year if day.month >= APRIL else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def format_inr(paise: int) -> str:
    """1,00,000.00: grouped in thousands, then lakhs and crores."""
    rupees, cents = divmod(paise, 100)
    digits = str(rupees)
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > LAKH_GROUP:
        groups.insert(0, head[-LAKH_GROUP:])
        head = head[:-LAKH_GROUP]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail]) + f".{cents:02d}"


def _words(number: int) -> str:
    # num2words writes "one thousand, five hundred and fifty"; a receipt
    # reads "One Thousand Five Hundred Fifty".
    text = num2words(number, lang="en_IN").replace(",", "").replace(" and ", " ")
    return text.title()


def in_words(paise: int) -> str:
    rupees, cents = divmod(paise, 100)
    text = f"Rupees {_words(rupees)}"
    if cents:
        text += f" and {_words(cents)} Paise"
    return text + " Only"
