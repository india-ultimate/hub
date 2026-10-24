import re

from server.utils import slugify_max


def slug_base(first_name: str, last_name: str) -> str:
    return slugify_max(f"{first_name} {last_name}", 50) or "player"


def unique_slug(base: str, taken: set[str]) -> str:
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


def has_base(slug: str | None, base: str) -> bool:
    return slug is not None and re.fullmatch(f"{re.escape(base)}(-\\d+)?", slug) is not None
