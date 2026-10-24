import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

from django.core import signing
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.timezone import now

from server.core.models import User
from server.mcp.auth import TokenInfo
from server.mcp.dispatch import call_api
from server.mcp.models import McpNonce
from server.mcp.private import scrub
from server.mcp.registry import ToolContext
from server.utils import IMAGE_TYPES, MAX_UPLOAD_BYTES, PDF_TYPE

SALT = "mcp-upload"
MAX_AGE = 900
USED = "This upload link was already used. Ask for a new one."
IMAGES = ",".join(IMAGE_TYPES)
DOCUMENT = ",".join((*IMAGE_TYPES, PDF_TYPE))
HINTS = {PDF_TYPE: "A PDF", IMAGES: "An image", DOCUMENT: "An image or a PDF"}
NAMES = {
    "accreditation": "accreditation certificate",
    "vaccination": "vaccination certificate",
    "college_id": "college ID",
    "profile_pic": "profile picture",
    "image": "logo",
    "new_team": "team logo",
}


@dataclass(frozen=True)
class Kind:
    path: str
    part: str | None
    files: dict[str, str]
    done: str


KINDS = {
    "accreditation": Kind(
        "/api/accreditation", "accreditation", {"certificate": PDF_TYPE}, "Accreditation saved."
    ),
    "college_id": Kind(
        "/api/college-id",
        "college_id",
        {"card_front": IMAGES, "card_back": IMAGES},
        "College ID saved.",
    ),
    "vaccination": Kind(
        "/api/vaccination", "vaccination", {"certificate": DOCUMENT}, "Vaccination saved."
    ),
    "profile_pic": Kind(
        "/api/profile-pic", None, {"profile_pic": IMAGES}, "Profile picture saved."
    ),
    "team_logo": Kind("/api/teams/edit", "team_details", {"image": IMAGES}, "Team logo saved."),
    "new_team": Kind("/api/teams", "team_details", {"image": IMAGES}, "Team created."),
}


def mint(user_pk: int, kind: str, ids: dict[str, int], part: dict[str, Any] | None) -> str:
    target = {"ids": ids, "part": json.dumps(part) if part is not None else None}
    return signing.dumps(
        {"u": user_pk, "k": kind, "f": target, "n": secrets.token_hex(16)}, salt=SALT
    )


def _error(status: int, message: str) -> JsonResponse:
    return JsonResponse({"ok": False, "message": scrub(message)}, status=status)


def upload(request: HttpRequest, token: str) -> HttpResponse:
    # A person opening the link gets Hub's own upload page, which asks here for JSON.
    if request.method == "GET" and "application/json" not in request.headers.get("Accept", ""):
        return redirect(f"/upload/{quote(token, safe=':')}")
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired:
        return _error(HTTPStatus.GONE, "This upload link has expired. Ask for a new one.")
    except signing.BadSignature:
        return _error(HTTPStatus.NOT_FOUND, "This upload link is not valid.")
    kind = KINDS.get(payload["k"])
    owner = User.objects.filter(pk=payload["u"], is_active=True).first()
    if kind is None or owner is None:
        return _error(HTTPStatus.GONE, "This upload link is no longer valid.")
    if request.method == "GET":
        return _describe(request, payload, kind, owner)
    if request.method != "POST":
        return HttpResponse(status=HTTPStatus.METHOD_NOT_ALLOWED)
    return _receive(request, payload, kind, owner)


def _describe(
    request: HttpRequest, payload: dict[str, Any], kind: Kind, owner: User
) -> JsonResponse:
    if McpNonce.objects.filter(key=payload["n"]).exists():
        return _error(HTTPStatus.GONE, USED)
    mine = request.user.is_authenticated and request.user.pk == owner.pk
    return JsonResponse(
        {
            "ok": True,
            "what": _name(payload["k"]),
            "mine": mine,
            "sign_in_as": None if mine else owner.get_full_name() or "another Hub account",
            "max_bytes": MAX_UPLOAD_BYTES,
            "fields": [
                {
                    "name": name,
                    "label": _name(name).capitalize(),
                    "accept": accept,
                    "hint": HINTS[accept],
                }
                for name, accept in kind.files.items()
            ],
        }
    )


def _name(key: str) -> str:
    return NAMES.get(key, key.replace("_", " "))


def _receive(request: HttpRequest, payload: dict[str, Any], kind: Kind, user: User) -> HttpResponse:
    sent = set(request.FILES)
    if sent != set(kind.files):
        return _error(
            HTTPStatus.BAD_REQUEST,
            f"Send exactly these files: {', '.join(sorted(kind.files))}.",
        )
    files = {name: cast(UploadedFile, request.FILES[name]) for name in kind.files}
    for name, file in files.items():
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            limit = MAX_UPLOAD_BYTES // (1024 * 1024)
            return _error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"The {_name(name)} must not exceed {limit} MB.",
            )

    ctx = ToolContext(
        user=user,
        token=TokenInfo(user, frozenset({"hub:write"}), "upload"),
        modern=True,
        client_capabilities={},
        input_responses=None,
        request_state=None,
        tool_name="create_upload_link",
        outer=request,
    )
    target = payload["f"]
    ids: dict[str, int] = target["ids"]
    body = {kind.part: target["part"]} if kind.part and target["part"] else {}
    with transaction.atomic():
        try:
            with transaction.atomic():
                McpNonce.objects.create(
                    key=payload["n"], expires_at=now() + timedelta(seconds=MAX_AGE * 2)
                )
        except IntegrityError:
            return _error(HTTPStatus.GONE, USED)
        response = call_api(ctx, "POST", kind.path.format(**ids), body=body, files=files)
        if not response.ok:
            transaction.set_rollback(True)
    if not response.ok:
        client_error = HTTPStatus.BAD_REQUEST <= response.status < HTTPStatus.INTERNAL_SERVER_ERROR
        status = response.status if client_error else HTTPStatus.BAD_GATEWAY
        return _error(status, response.message)
    named = dict(ids)
    if isinstance(response.data, dict) and payload["k"] == "new_team":
        named |= {"team_id": response.data["id"], "team_slug": response.data["slug"]}
    return JsonResponse({"ok": True, "message": kind.done, **named})
