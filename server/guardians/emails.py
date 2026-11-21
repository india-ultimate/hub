"""The email that asks a guardian to sign a ward's waiver."""

import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from server.core.models import Guardianship
from server.guardians import tokens
from server.task.helpers import queue_emails

RESEND_AFTER = datetime.timedelta(minutes=10)


def may_send(g: Guardianship) -> bool:
    return g.link_sent_at is None or now() - g.link_sent_at > RESEND_AFTER


def send_link(g: Guardianship) -> None:
    """Stamp the row, which retires any earlier link, and email a new one."""
    g.link_sent_at = now()
    g.save(update_fields=["link_sent_at"])
    if "@" not in (g.user.email or ""):
        return
    player = g.player
    ward_name = player.user.get_full_name()
    context = {
        "first_name": g.user.first_name or "there",
        "ward_name": ward_name,
        "link_url": f"{settings.PUBLIC_URL}/guardian/{tokens.mint(g)}",
        "login_url": f"{settings.PUBLIC_URL}/login?redirect=/waiver/{player.id}",
        "has_subscription": player.current_subscription is not None,
    }
    html = render_to_string("emails/guardian_link.html", context)
    message = EmailMultiAlternatives(
        subject=f"Please sign {player.user.first_name}'s waiver for India Ultimate",
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[g.user.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])
