"""Shrink an image over the free plan's limits, which Cloudinary refuses."""

import contextlib
import fcntl
import io
import logging
import math
from collections.abc import Iterator
from typing import IO

from PIL import Image, ImageOps

MAX_PIXELS = 25_000_000
MAX_BYTES = 10_000_000
# What fits beside the workers on a 1 GB machine with no swap; the rest goes as is.
MAX_PEAK_BYTES = 460_000_000
# Others (EPS runs Ghostscript) are left to Cloudinary, whatever the extension.
# JPEG covers MPO, the format many phones save their photos in.
# Not WEBP: Pillow's decoder needs ~1 GB for one over 25 MP.
FORMATS = ["JPEG", "PNG", "GIF", "BMP", "TIFF"]
Image.init()  # so all of them are registered, not just the common few

logger = logging.getLogger(__name__)


def peak_bytes(mode: str, pixels: int) -> float:
    """Roughly what shrinking takes at its peak, measured on Pillow 10.4."""
    # Bytes a pixel as Pillow holds each mode (P is resized as it is).
    per_pixel = 1 if mode in {"1", "L", "P"} else 2 if mode.startswith("I;16") else 4
    # Transparent images are copied premultiplied before resizing.
    transparent = mode in {"RGBA", "LA", "PA"}
    return pixels * per_pixel * (4.0 if transparent else 2.3)


@contextlib.contextmanager
def _one_at_a_time() -> Iterator[None]:
    # A full decode can take hundreds of MB: one per machine, not per thread.
    # This file itself is the lock: always there, and readable by every user.
    with open(__file__, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def shrunk(f: IO[bytes]) -> io.BytesIO | None:
    """A copy of the image within the limits, or None to upload it as it is."""
    size = f.seek(0, io.SEEK_END)
    f.seek(0)
    out = io.BytesIO()
    try:
        image = Image.open(f, formats=FORMATS)
    except Exception:  # PDFs, SVGs, HEIC and other files
        f.seek(0)
        return None
    try:
        pixels = image.width * image.height
        if (
            (pixels <= MAX_PIXELS and size <= MAX_BYTES)
            or peak_bytes(image.mode, pixels) > MAX_PEAK_BYTES
            or image.mode.startswith("I;16")  # Pillow can't resize it
            or getattr(image, "is_animated", False)  # shrunk, only one frame would stay
        ):
            return None
        # ponytail: scaling by the byte ratio is a guess for PNGs; good enough
        # for the few files over 10 MB, which are photos.
        scale = min(math.sqrt(MAX_PIXELS / pixels) * 0.99, math.sqrt(MAX_BYTES / size) * 0.9)
        box = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        image_format = image.format
        options = {"quality": 90} if image_format in {"JPEG", "MPO"} else {}
        if icc_profile := image.info.get("icc_profile"):
            options["icc_profile"] = icc_profile  # or iPhone colours shift
        with _one_at_a_time():
            # thumbnail decodes JPEGs at a fraction of full size where it can.
            image.thumbnail(box, Image.Resampling.LANCZOS, reducing_gap=2.0)
            ImageOps.exif_transpose(image, in_place=True)  # or photos turn sideways
            image.save(out, format="JPEG" if image_format == "MPO" else image_format, **options)
    except Exception:  # what Pillow can't resize or save: Cloudinary decides
        logger.warning("Couldn't shrink an image; uploading it as it is", exc_info=True)
        return None
    finally:
        f.seek(0)
    out.seek(0)
    return out
