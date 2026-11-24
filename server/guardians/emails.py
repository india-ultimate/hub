"""The email that asks a guardian to sign a ward's waiver."""

import datetime
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from server.core.models import Guardianship, Player, User
from server.guardians import tokens
from server.task.helpers import queue_emails

RESEND_AFTER = datetime.timedelta(minutes=10)
TOO_SOON = "A link was just sent. You can send another in 10 minutes."


def _text(html: str) -> str:
    return strip_tags(re.sub(r"<style.*?</style>", "", html, flags=re.S))


def may_send(g: Guardianship) -> bool:
    return g.link_sent_at is None or now() - g.link_sent_at > RESEND_AFTER


def send_link(g: Guardianship, *, reuse: bool = False, by: User | None = None) -> bool:
    """Email a link; False if the guardian has no address to send to.

    A new stamp retires every earlier link. With `reuse`, a stamp whose link
    is still within MAX_AGE is kept, so the link already in the inbox keeps
    working.
    """
    if "@" not in (g.user.email or ""):
        return False
    stale = g.link_sent_at is None or now() - g.link_sent_at > tokens.MAX_AGE
    if stale or not reuse:
        g.link_sent_at = now()
    player = g.player
    ward_name = player.user.get_full_name()
    context = {
        "first_name": g.user.first_name or "there",
        "ward_name": ward_name,
        "by_name": (by.get_full_name() or by.get_username()) if by else ward_name,
        "link_url": f"{settings.PUBLIC_URL}/guardian/{tokens.mint(g)}",
        "login_url": f"{settings.PUBLIC_URL}/login?redirect=/waiver/{player.id}",
        "has_subscription": player.current_subscription is not None,
    }
    html = render_to_string("emails/guardian_link.html", context)
    message = EmailMultiAlternatives(
        subject=f"Please sign {player.user.first_name}'s waiver for India Ultimate",
        body=_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[g.user.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])
    g.save(update_fields=["link_sent_at"])
    return True


def send_changed(old: User, g: Guardianship, by: User) -> None:
    """Tell a replaced guardian who replaced them."""
    if "@" not in (old.email or ""):
        return
    ward_first = g.player.user.first_name
    html = render_to_string(
        "emails/guardian_changed.html",
        {
            "first_name": old.first_name or "there",
            "by_name": by.get_full_name() or by.get_username(),
            "by_is_ward": by.pk == g.player.user_id,
            "ward_first_name": ward_first,
            "new_name": g.user.get_full_name() or g.user.get_username(),
        },
    )
    message = EmailMultiAlternatives(
        subject=f"{ward_first}'s guardian was changed",
        body=_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[old.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])


def send_waiver_reminder(player: Player, by: User, team_name: str) -> bool:
    """Ask a player to sign their own waiver, naming who asked."""
    if "@" not in (player.user.email or ""):
        return False
    html = render_to_string(
        "emails/waiver_reminder.html",
        {
            "first_name": player.user.first_name or "there",
            "by_name": by.get_full_name() or by.get_username(),
            "team_name": team_name,
            "waiver_url": f"{settings.PUBLIC_URL}/waiver/{player.id}",
        },
    )
    message = EmailMultiAlternatives(
        subject="Please sign your India Ultimate waiver",
        body=_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])
    return True
