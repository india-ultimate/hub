import datetime
from typing import Any

from django.core import signing

from server.core.models import Guardianship
from server.guardians.access import minor_cutoff

SALT = "guardian-link"
MAX_AGE = datetime.timedelta(days=7)


def mint(g: Guardianship) -> str:
    assert g.link_sent_at is not None  # noqa: S101 - callers stamp the row first
    return signing.dumps({"g": g.pk, "u": g.user_id, "s": g.link_sent_at.isoformat()}, salt=SALT)


def inspect(token: str) -> tuple[Guardianship | None, bool]:
    """The guardianship a link names, and whether the link can still be used."""
    expired = False
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired:
        expired = True
        payload = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None, False
    g = Guardianship.objects.select_related("player").filter(pk=payload["g"]).first()
    if g is None:
        return None, False
    return g, not expired and _usable(g, payload)


def _usable(g: Guardianship, payload: dict[str, Any]) -> bool:
    if g.user_id != payload["u"] or g.link_sent_at is None:
        return False
    if g.link_sent_at.isoformat() != payload["s"]:
        return False
    player = g.player
    if g.user_id == player.user_id or player.date_of_birth <= minor_cutoff():
        return False
    sub = player.current_subscription
    return not (sub and sub.waiver_valid and sub.coc_agreed)
