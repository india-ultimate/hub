"""What is sent when a subscription starts or changes."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from server.core.models import Player, User
from server.season.models import Season
from server.subscription.models import Subscription
from server.task.helpers import queue_emails

CONFIRMATION_SUBJECT = "Your India Ultimate subscription"
SPONSORSHIP_RESET_SUBJECT = "Your discounted subscription now renews each season"
CODE_OF_CONDUCT_SUBJECT = "Please agree to the India Ultimate code of conduct"


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
        "coc_agreed": subscription.coc_agreed,
        "coc_url": f"{settings.EMAIL_INVITATION_BASE_URL}/code-of-conduct/{player.id}",
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


def build_sponsorship_reset(player: Player, season: Season) -> EmailMultiAlternatives:
    """Sponsorship used to carry over for good; now it is granted one season
    at a time, so tell someone who had it how to ask for this one."""
    context = {
        "first_name": player.user.first_name,
        "season": season.name,
        "subscription_url": f"{settings.EMAIL_INVITATION_BASE_URL}/subscription/{player.id}",
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


def build_code_of_conduct_request(
    player: Player, season: Season, to: User
) -> EmailMultiAlternatives:
    """Asks someone to agree to this season's code of conduct: the player,
    or a minor's guardian on their behalf."""
    context = {
        "first_name": to.first_name or "there",
        "player_name": player.user.get_full_name(),
        "for_minor": to != player.user,
        "season": season.name,
        "coc_url": f"{settings.EMAIL_INVITATION_BASE_URL}/code-of-conduct/{player.id}",
    }
    html = render_to_string("emails/code_of_conduct_request.html", context)
    message = EmailMultiAlternatives(
        subject=CODE_OF_CONDUCT_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[to.email],
    )
    message.attach_alternative(html, "text/html")
    return message
