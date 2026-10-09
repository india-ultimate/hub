"""How a Django file name maps to a Cloudinary id, type and URL.

The storage class, the copy command and the old-link redirect all use these,
so a name always lands in, and is served from, the same place.
"""

from typing import Any

from django.conf import settings

PREFIX = "media/"
# Stored as Cloudinary "image" (which also serves PDFs and SVGs); the rest raw.
IMAGE_EXTENSIONS = frozenset(
    {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "heic", "svg", "pdf"}
)
# Readable, at a fraction of a phone photo's size.
COLLEGE_ID_RESIZE = [{"width": 1600, "height": 1600, "crop": "limit"}, {"quality": "auto"}]


def _split(name: str) -> tuple[str, str]:
    """(stem, extension in lower case), with "" for no extension."""
    if "." not in name.rpartition("/")[2]:
        return name, ""
    stem, _, ext = name.rpartition(".")
    return stem, ext.lower()


def resource_type(name: str) -> str:
    return "image" if _split(name)[1] in IMAGE_EXTENSIONS else "raw"


def public_id(name: str) -> str:
    stem, _ = _split(name)
    return PREFIX + (stem if resource_type(name) == "image" else name)


def url(name: str) -> str:
    stem, ext = _split(name)
    kind = resource_type(name)
    path = f"{stem}.{ext}" if kind == "image" else name
    return (
        f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/{kind}/upload/{PREFIX}{path}"
    )


def upload_options(name: str) -> dict[str, Any]:
    return {"transformation": COLLEGE_ID_RESIZE} if name.startswith("college_ids/") else {}
