"""Shrink an image over the free plan's limits, which Cloudinary refuses."""

import contextlib
import fcntl
import io
import math
import os
import tempfile
from collections.abc import Iterator
from typing import IO

from PIL import Image, ImageOps

MAX_PIXELS = 25_000_000
MAX_BYTES = 10_000_000
# Past this, decoding alone takes gigabytes: left to Cloudinary to refuse.
MAX_DECODE_PIXELS = 100_000_000
LOCK = os.path.join(tempfile.gettempdir(), "hub-shrink.lock")


@contextlib.contextmanager
def _one_at_a_time() -> Iterator[None]:
    # A full decode can take hundreds of MB: one per machine, not per thread.
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def shrunk(f: IO[bytes]) -> io.BytesIO | None:
    """A copy of the image within the limits, or None to upload it as it is."""
    size = f.seek(0, io.SEEK_END)
    f.seek(0)
    out = io.BytesIO()
    try:
        image = Image.open(f)
        pixels = image.width * image.height
        if pixels > MAX_DECODE_PIXELS or (pixels <= MAX_PIXELS and size <= MAX_BYTES):
            return None
        # ponytail: scaling by the byte ratio is a guess for PNGs; good enough
        # for the few files over 10 MB, which are photos.
        scale = min(math.sqrt(MAX_PIXELS / pixels) * 0.99, math.sqrt(MAX_BYTES / size) * 0.9)
        box = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        image_format = image.format
        options = {"quality": 90} if image_format in {"JPEG", "WEBP"} else {}
        if icc_profile := image.info.get("icc_profile"):
            options["icc_profile"] = icc_profile  # or iPhone colours shift
        with _one_at_a_time():
            # thumbnail decodes JPEGs at a fraction of full size where it can.
            image.thumbnail(box, Image.Resampling.LANCZOS, reducing_gap=2.0)
            upright = ImageOps.exif_transpose(image) or image  # or photos turn sideways
            upright.save(out, format=image_format, **options)
    except Exception:  # PDFs, SVGs, HEIC, or what Pillow can't resize or save
        return None
    finally:
        f.seek(0)
    out.seek(0)
    return out
