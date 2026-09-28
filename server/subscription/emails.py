"""What is sent when a subscription starts or changes."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from server.subscription.models import Subscription
from server.task.helpers import queue_emails

CONFIRMATION_SUBJECT = "Your India Ultimate subscription"


def build_confirmation(subscription: Subscription) -> EmailMultiAlternatives:
    player = subscription.player
    context = {
        "first_name": player.user.first_name,
        "season": subscription.season.name,
        "tier": subscription.plan.type.name if subscription.plan is not None else "Subscription",
        "iu_id": player.iu_id,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "waiver_signed": subscription.waiver_valid,
        "waiver_url": f"{settings.EMAIL_INVITATION_BASE_URL}/waiver/{player.id}",
    }
    html = render_to_string("emails/subscription_confirmation.html", context)
    message = EmailMultiAlternatives(
        subject=CONFIRMATION_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    return message


def queue_confirmation(subscription: Subscription) -> None:
    """One message per subscription created or upgraded."""
    if "@" not in (subscription.player.user.email or ""):
        return
    queue_emails([build_confirmation(subscription)])
