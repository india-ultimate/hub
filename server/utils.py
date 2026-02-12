import datetime

from django.template.defaultfilters import slugify


def mask_string(s: str) -> str:
    n = len(s)
    long_str = 8
    medium_str = 6
    if n >= long_str:
        return s[:2] + "x" * (n - 4) + s[-2:]
    elif n >= medium_str:
        return s[:1] + "x" * (n - 2) + s[-1:]
    else:
        return s[:1] + "x" * (n - 1)


def ordinal_suffix(num: int) -> str:
    """Get ordinal suffix for a number. 22 -> 22nd, 103 -> 103rd..."""

    # all numbers with last 2 digits in range 10 to 20 will have 'th' as suffix
    # 13th, 111th, 1012th, 12233036th....
    if 10 < num % 100 < 20:  # noqa: PLR2004
        return "th"

    # if last 2 digits arent within 10..20,
    # nums ending with 1, 2, 3 have the below suffixes
    number_suffixes = {1: "st", 2: "nd", 3: "rd"}
    if 1 <= num % 10 <= 3:  # noqa: PLR2004
        return number_suffixes[num % 10]

    # all other numbers have 'th' as suffix
    return "th"


def today() -> datetime.date:
    ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
    return datetime.datetime.now(ind_tz).date()


def if_dates_are_not_in_order(first_date: str, second_date: str) -> bool:
    ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
    return (
        datetime.datetime.strptime(first_date, "%Y-%m-%d").astimezone(ind_tz).date()
        > datetime.datetime.strptime(second_date, "%Y-%m-%d").astimezone(ind_tz).date()
    )


def if_today(date: str) -> bool:
    ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
    return (
        datetime.datetime.strptime(date, "%Y-%m-%d").astimezone(ind_tz).date()
        == datetime.datetime.now(ind_tz).date()
    )


def is_today_in_between_dates(from_date: datetime.date, to_date: datetime.date) -> bool:
    return from_date <= today() <= to_date


def calculate_late_penalty(
    reg_end_date: datetime.date,
    penalty_per_day: int,
    penalty_end_date: datetime.date | None = None,
) -> tuple[int, int]:
    """Returns (days_late, penalty_amount_in_paise). Both 0 if not late.

    Uses IST (India Standard Time) for date comparison via today().
    """
    current_date = today()
    if current_date <= reg_end_date or penalty_per_day <= 0:
        return 0, 0
    if penalty_end_date and current_date > penalty_end_date:
        return 0, 0
    days_late = (current_date - reg_end_date).days
    return days_late, days_late * penalty_per_day


def default_invitation_expiry_date() -> datetime.date:
    return today() + datetime.timedelta(days=4)


def slugify_max(text: str, max_length: int = 50) -> str:
    slug = slugify(text)
    if len(slug) <= max_length:
        return str(slug)
    trimmed_slug = slug[:max_length].rsplit("-", 1)[0]
    if len(trimmed_slug) <= max_length:
        return trimmed_slug
    # First word is > max_length chars, so we have to break it
    return slug[:max_length]
