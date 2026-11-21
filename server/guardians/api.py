"""The pages a guardian lands on from the link in their email."""

from django.contrib.auth import login
from django.http import HttpRequest
from ninja import Router, Schema

from server.core.models import User
from server.duplicates.players.identity import mask_email
from server.guardians import tokens
from server.types import message_response

link_router = Router()


class LinkSchema(Schema):
    valid: bool
    ward_first_name: str
    guardian_name: str
    guardian_email_masked: str
    player_id: int
    signed_in_as_guardian: bool
    signed_in_name: str | None


class RedirectSchema(Schema):
    redirect: str


@link_router.get("/link/{token}", auth=None, response={200: LinkSchema, 404: message_response})
def view_link(request: HttpRequest, token: str) -> tuple[int, dict[str, object]]:
    g, valid = tokens.inspect(token)
    if g is None:
        return 404, {"message": "This link is not valid."}
    viewer = request.user if request.user.is_authenticated else None
    as_guardian = viewer is not None and viewer.pk == g.user_id
    other = viewer if viewer is not None and not as_guardian else None
    return 200, {
        "valid": valid,
        "ward_first_name": g.player.user.first_name,
        "guardian_name": g.user.get_full_name() or g.user.first_name,
        "guardian_email_masked": mask_email(g.user.email),
        "player_id": g.player_id,
        "signed_in_as_guardian": as_guardian,
        "signed_in_name": (other.get_full_name() or other.get_username()) if other else None,
    }


@link_router.post(
    "/link/{token}",
    auth=None,
    response={
        200: RedirectSchema,
        403: message_response,
        404: message_response,
        410: message_response,
    },
)
def use_link(request: HttpRequest, token: str) -> tuple[int, dict[str, str]]:
    g, valid = tokens.inspect(token)
    if g is None:
        return 404, {"message": "This link is not valid."}
    if not valid or not g.user.is_active:
        return 410, {"message": "This link has expired or was already used."}
    user: User = g.user
    if user.is_staff or user.is_superuser:
        return 403, {"message": "Staff accounts sign in the normal way."}
    request.user = user
    login(request, user)
    return 200, {"redirect": f"/waiver/{g.player_id}"}
