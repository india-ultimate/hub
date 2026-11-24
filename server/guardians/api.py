"""The pages a guardian lands on from the link in their email."""

import datetime
import logging
from typing import Any, cast

from django.contrib.auth import login
from django.core.cache import cache
from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from server.core.accounts import find_login_user, resolve_login_user
from server.core.models import Guardianship, Player, User
from server.duplicates.players.identity import mask_email
from server.guardians import emails, tokens
from server.guardians.access import may_manage_guardian, minor_cutoff
from server.types import message_response

logger = logging.getLogger(__name__)

link_router = Router()
guardian_router = Router()


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
        return 410, {"message": "This link has expired, or a newer link was sent."}
    user: User = g.user
    if user.is_staff or user.is_superuser:
        return 403, {"message": "Please sign in with your email and a code instead."}
    request.user = user
    login(request, user)
    return 200, {"redirect": f"/waiver/{g.player_id}"}


class GuardianIn(Schema):
    first_name: str
    last_name: str
    email: str
    phone: str = ""
    relation: Guardianship.Relation


class GuardianSchema(Schema):
    name: str
    first_name: str
    last_name: str
    phone: str
    email: str
    relation: str
    link_sent_at: datetime.datetime | None
    is_minor: bool
    is_self: bool


class SignedSchema(Schema):
    done: bool
    by_name: str | None
    at: datetime.datetime | None


class GuardianStatusSchema(Schema):
    guardian: GuardianSchema | None
    waiver: SignedSchema | None
    coc: SignedSchema | None
    can_change: bool
    can_resend: bool


def _signed(done: bool, by: User | None, at: datetime.datetime | None) -> dict[str, object]:
    return {
        "done": done,
        "by_name": (by.get_full_name() or by.get_username()) if by else None,
        "at": at,
    }


def _status(player: Player) -> dict[str, object]:
    g = Guardianship.objects.filter(player=player).select_related("user").first()
    sub = player.current_subscription
    is_self = g is not None and g.user_id == player.user_id
    guardian = None
    if g is not None:
        guardian = {
            "name": g.user.get_full_name() or g.user.get_username(),
            "first_name": g.user.first_name,
            "last_name": g.user.last_name,
            "phone": g.user.phone,
            "email": g.user.email,
            "relation": g.relation,
            "link_sent_at": g.link_sent_at,
            "is_minor": Player.objects.filter(
                user=g.user, date_of_birth__gt=minor_cutoff()
            ).exists(),
            "is_self": is_self,
        }
    return {
        "guardian": guardian,
        "waiver": sub and _signed(sub.waiver_valid, sub.waiver_signed_by, sub.waiver_signed_at),
        "coc": sub and _signed(sub.coc_agreed, sub.coc_agreed_by, sub.coc_agreed_at),
        "can_change": True,
        "can_resend": g is not None and not is_self,
    }


def _changes_this_hour(player: Player) -> int:
    key = _CHANGES_KEY.format(player.pk)
    cache.add(key, 0, 3600)
    try:
        return int(cache.incr(key))
    except ValueError:  # a cache that stores nothing, as in tests
        return 1


def _managed(player_id: int) -> Player:
    return get_object_or_404(Player.objects.select_related("user"), pk=player_id)


MAX_CHANGES_PER_HOUR = 3
_CHANGES_KEY = "guardian-changes:{}"

_FORBIDDEN = (403, {"message": "You can't manage this player's guardian."})


@guardian_router.get(
    "/{player_id}/guardian",
    response={200: GuardianStatusSchema, 403: message_response, 404: message_response},
)
def get_guardian(request: HttpRequest, player_id: int) -> tuple[int, dict[str, Any]]:
    player = _managed(player_id)
    if not may_manage_guardian(request.user, player):
        return _FORBIDDEN
    return 200, _status(player)


@guardian_router.put(
    "/{player_id}/guardian",
    response={
        200: GuardianStatusSchema,
        400: message_response,
        403: message_response,
        404: message_response,
        429: message_response,
    },
)
def put_guardian(
    request: HttpRequest, player_id: int, data: GuardianIn
) -> tuple[int, dict[str, Any]]:
    player = _managed(player_id)
    if not may_manage_guardian(request.user, player):
        return _FORBIDDEN
    email = data.email.strip().lower()
    if "@" not in email:
        return 400, {"message": "Enter a valid email address"}
    existing = find_login_user(email)
    if existing is not None:
        if existing.pk == player.user_id:
            first = player.user.first_name
            return 400, {
                "message": f"That's {first}'s own account. A guardian needs their own email."
            }
        if Player.objects.filter(user=existing, date_of_birth__gt=minor_cutoff()).exists():
            return 400, {
                "message": "A guardian must be 18 or older. Please use a parent or another adult."
            }
    current = Guardianship.objects.filter(player=player).select_related("user").first()
    if current is not None and existing is not None and current.user_id == existing.pk:
        current.relation = data.relation
        current.save(update_fields=["relation"])
        return 200, _status(player)
    if not request.user.is_staff and _changes_this_hour(player) > MAX_CHANGES_PER_HOUR:
        return 429, {"message": "You've changed your guardian several times. Try again in an hour."}
    with transaction.atomic():
        user = resolve_login_user(
            email, first_name=data.first_name, last_name=data.last_name, phone=data.phone
        )
        old = current.user if current is not None else None
        g, _ = Guardianship.objects.update_or_create(
            player=player, defaults={"user": user, "relation": data.relation, "link_sent_at": None}
        )
    try:
        emails.send_link(g, by=cast(User, request.user))
    except Exception:
        logger.exception("Couldn't email the new guardian of player %s", player.pk)
    if old is not None:
        try:
            emails.send_changed(old, g, by=cast(User, request.user))
        except Exception:
            logger.exception("Couldn't tell the old guardian of player %s", player.pk)
    return 200, _status(player)


@guardian_router.post(
    "/{player_id}/guardian/link",
    response={
        200: message_response,
        400: message_response,
        403: message_response,
        404: message_response,
        429: message_response,
    },
)
def resend_guardian_link(request: HttpRequest, player_id: int) -> tuple[int, dict[str, str]]:
    player = _managed(player_id)
    if not may_manage_guardian(request.user, player):
        return _FORBIDDEN
    g = Guardianship.objects.filter(player=player).select_related("user").first()
    if g is None:
        return 400, {"message": "Add a guardian first"}
    if g.user_id == player.user_id:
        return 400, {"message": "A player cannot be their own guardian."}
    sub = player.current_subscription
    if sub is not None and not emails.to_sign(sub):
        return 400, {"message": "Nothing is left to sign."}
    if not emails.may_send(g):
        return 429, {"message": emails.TOO_SOON}
    try:
        sent = emails.send_link(g)
    except Exception:
        logger.exception("Couldn't email the guardian of player %s", player.pk)
        return 400, {"message": "Couldn't send the email. Try again in a moment."}
    if not sent:
        return 400, {"message": "We have no email address for this guardian. Please change them."}
    return 200, {"message": f"Link sent to {g.user.email}"}
