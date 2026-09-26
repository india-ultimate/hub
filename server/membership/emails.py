"""What is sent when a membership starts or changes."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from server.core.models import Player
from server.membership.models import Membership
from server.season.models import Season
from server.task.helpers import queue_emails

CONFIRMATION_SUBJECT = "Your India Ultimate membership"
SPONSORSHIP_RESET_SUBJECT = "Your discounted membership now renews each season"


def build_confirmation(membership: Membership) -> EmailMultiAlternatives:
    player = membership.player
    context = {
        "first_name": player.user.first_name,
        "season": membership.season.name,
        "tier": membership.plan.type.name if membership.plan is not None else "Membership",
        "membership_number": player.membership_number,
        "start_date": membership.start_date,
        "end_date": membership.end_date,
        "waiver_signed": membership.waiver_valid,
        "waiver_url": f"{settings.EMAIL_INVITATION_BASE_URL}/waiver/{player.id}",
    }
    html = render_to_string("emails/membership_confirmation.html", context)
    message = EmailMultiAlternatives(
        subject=CONFIRMATION_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    return message


def queue_confirmation(membership: Membership) -> None:
    """One message per membership created or upgraded."""
    if "@" not in (membership.player.user.email or ""):
        return
    queue_emails([build_confirmation(membership)])


def build_sponsorship_reset(player: Player, season: Season) -> EmailMultiAlternatives:
    """Sponsorship used to carry over for good; now it is granted one season
    at a time, so tell someone who had it how to ask for this one."""
    context = {
        "first_name": player.user.first_name,
        "season": season.name,
        "membership_url": f"{settings.EMAIL_INVITATION_BASE_URL}/membership/{player.id}",
    }
    html = render_to_string("emails/sponsorship_reset.html", context)
    message = EmailMultiAlternatives(
        subject=SPONSORSHIP_RESET_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    return message
