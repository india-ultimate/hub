"""Shrink an image over the free plan's limits, which Cloudinary refuses."""

import io
import math
from typing import IO

from PIL import Image, ImageOps

MAX_PIXELS = 25_000_000
MAX_BYTES = 10_000_000


def _over_limits(f: IO[bytes]) -> tuple[Image.Image, int] | None:
    """The image and its byte size if it's over the limits, else None."""
    size = f.seek(0, io.SEEK_END)
    f.seek(0)
    try:
        image = Image.open(f)
    except Exception:  # PDFs, SVGs, HEIC and other files: left to Cloudinary
        image = None
    f.seek(0)
    if image is None or (image.width * image.height <= MAX_PIXELS and size <= MAX_BYTES):
        return None
    return image, size


def too_big(f: IO[bytes]) -> bool:
    return _over_limits(f) is not None


def shrunk(f: IO[bytes]) -> io.BytesIO | None:
    """A copy of the image within the limits, or None if it fits already."""
    over = _over_limits(f)
    if over is None:
        return None
    image, size = over
    # ponytail: scaling by the byte ratio is a guess for PNGs; good enough
    # for the few files over 10 MB, which are photos.
    scale = min(
        math.sqrt(MAX_PIXELS / (image.width * image.height)) * 0.99,
        math.sqrt(MAX_BYTES / size) * 0.9,
        1,
    )
    image_format = image.format
    upright = ImageOps.exif_transpose(image) or image  # or phone photos turn sideways
    width, height = max(1, int(upright.width * scale)), max(1, int(upright.height * scale))
    out = io.BytesIO()
    resized = upright.resize((width, height), Image.Resampling.LANCZOS)
    resized.save(out, format=image_format, quality=90)
    out.seek(0)
    f.seek(0)
    return out
