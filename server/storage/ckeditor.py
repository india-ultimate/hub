"""CKEditor's uploads (the admin's rich text), refused in its own words past
the server's limits, rather than with a 413 or a 500."""

import json
import logging

import cloudinary.exceptions
from ckeditor_uploader import views as ckeditor_views
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
# What Cloudinary takes after the server's shrink: 50 MP for most photos, ~28 MP
# for transparent ones, and only its own 25 MP for what isn't shrunk.
MAX_PIXELS = 50_000_000
MAX_TRANSPARENT_PIXELS = 28_000_000
MAX_CLOUDINARY_PIXELS = 25_000_000
UNSHRUNK_FORMATS = {"WEBP", "GIF"}

logger = logging.getLogger(__name__)


def upload_error(file: UploadedFile) -> str:
    if file.size and file.size > MAX_UPLOAD_BYTES:
        return "Files must be 10 MB or smaller."
    try:
        with Image.open(file) as image:  # reads the header, not the pixels
            limit = (
                MAX_CLOUDINARY_PIXELS
                if image.format in UNSHRUNK_FORMATS
                else MAX_TRANSPARENT_PIXELS if image.mode in {"RGBA", "LA", "PA"} else MAX_PIXELS
            )
            pixels = image.width * image.height
    except Image.DecompressionBombError:
        limit, pixels = MAX_PIXELS, MAX_PIXELS + 1
    except Exception:  # not an image: Cloudinary decides
        return ""
    finally:
        file.seek(0)
    if pixels > limit:
        return f"This photo is too large; please use one under {limit // 1_000_000} megapixels."
    return ""


def refused(request: HttpRequest, message: str) -> HttpResponse:
    func_num = request.GET.get("CKEditorFuncNum")
    if func_num and func_num.isascii() and func_num.isdigit():  # the upload dialog
        script = (
            f'window.parent.CKEDITOR.tools.callFunction({func_num}, "", {json.dumps(message)});'
        )
        return HttpResponse(f"<script>{script}</script>")
    return JsonResponse({"uploaded": 0, "error": {"message": message}})  # drag and drop


@csrf_exempt
@staff_member_required
def upload(request: HttpRequest) -> HttpResponse:
    file = request.FILES.get("upload")
    if file and (error := upload_error(file)):
        return refused(request, error)
    try:
        return ckeditor_views.upload(request)
    except cloudinary.exceptions.Error:
        logger.exception("Cloudinary refused a CKEditor upload")
        return refused(request, "Couldn't save the file. Try again.")
