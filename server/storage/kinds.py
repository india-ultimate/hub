"""How a Django file name maps to a Cloudinary id, type and URL.

The storage class, the copy command and the old-link redirect all use these,
so a name always lands in, and is served from, the same place.
"""

from typing import Any
from urllib.parse import quote

from django.conf import settings

PREFIX = "media/"
# Stored as Cloudinary "image" (which also serves PDFs and SVGs); the rest raw.
IMAGE_EXTENSIONS = frozenset(
    {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "heic", "svg", "pdf"}
)
# Readable, at a fraction of a phone photo's size.
COLLEGE_ID_RESIZE = [{"width": 1600, "height": 1600, "crop": "limit"}, {"quality": "auto"}]


def _split(name: str) -> tuple[str, str]:
    """(stem, extension as written), with "" for no extension."""
    if "." not in name.rpartition("/")[2]:
        return name, ""
    stem, _, ext = name.rpartition(".")
    return stem, ext


def resource_type(name: str) -> str:
    return "image" if _split(name)[1].lower() in IMAGE_EXTENSIONS else "raw"


def public_id(name: str) -> str:
    """The extension stays in the id (back.jpeg -> back_jpeg) so names that
    differ only by extension, like back.jpg and back.jpeg, never share a file.
    Image extensions have no "_", so the mapping can't collide."""
    if resource_type(name) == "raw":
        return PREFIX + name
    stem, ext = _split(name)
    return f"{PREFIX}{stem}_{ext}"


def url(name: str) -> str:
    kind = resource_type(name)
    path = public_id(name)
    if kind == "image":
        path += "." + _split(name)[1].lower()
    return (
        f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/{kind}/upload/{quote(path)}"
    )


def stored_format(name: str) -> str | None:
    """The format to keep an image in: its name's, so its URL always works.

    Cloudinary keeps an image in its real format, and a .pdf that's a PNG
    then answers 401 at its .pdf URL (strict transformations are on).
    """
    if resource_type(name) != "image":
        return None
    ext = _split(name)[1].lower()
    return "jpg" if ext == "jpeg" else ext


def format_option(name: str) -> dict[str, str]:
    stored = stored_format(name)
    return {"format": stored} if stored else {}


def upload_options(name: str) -> dict[str, Any]:
    # Images only: Cloudinary refuses a transformation on a raw file.
    resize = name.startswith("college_ids/") and resource_type(name) == "image"
    return {"transformation": COLLEGE_ID_RESIZE} if resize else {}
