"""What is sent when a subscription starts or changes."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from server.core.models import Guardianship, Player, User
from server.guardians import tokens
from server.guardians.emails import build_link, to_do, to_sign
from server.season.models import Season
from server.subscription.models import Subscription
from server.task.helpers import html_to_text, queue_emails

logger = logging.getLogger(__name__)

CONFIRMATION_SUBJECT = "Your India Ultimate subscription"
SPONSORSHIP_RESET_SUBJECT = "Your discounted subscription now renews each season"
CODE_OF_CONDUCT_SUBJECT = "Please agree to the code of conduct"


def pending_guardian(subscription: Subscription) -> Guardianship | None:
    """The guardian who still has to sign for this minor: the waiver, the
    code of conduct, or both."""
    player = subscription.player
    g = Guardianship.objects.filter(player=player).select_related("user").first()
    if g is None or not player.is_minor or g.user_id == player.user_id:
        return None
    return g if to_sign(subscription) else None


def build_confirmation(subscription: Subscription) -> EmailMultiAlternatives:
    player = subscription.player
    g = pending_guardian(subscription)
    items = to_sign(subscription)
    emailed = g is not None and "@" in g.user.email
    context = {
        "site_url": settings.PUBLIC_URL,
        "first_name": player.user.first_name,
        "season": subscription.season.name,
        "plan": subscription.plan.type.name if subscription.plan is not None else "Subscription",
        "iu_id": player.iu_id,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date,
        "waiver_signed": subscription.waiver_valid,
        "coc_agreed": subscription.coc_agreed,
        "to_do": to_do(subscription, "your"),
        "guardian_name": (g.user.get_full_name() or "your guardian") if emailed and g else None,
        "needs_guardian": player.is_minor and bool(items) and not emailed,
        "waiver_url": f"{settings.PUBLIC_URL}/waiver/{player.id}",
        "coc_url": f"{settings.PUBLIC_URL}/code-of-conduct/{player.id}",
        "dashboard_url": f"{settings.PUBLIC_URL}/dashboard",
    }
    html = render_to_string("emails/subscription_confirmation.html", context)
    message = EmailMultiAlternatives(
        subject=CONFIRMATION_SUBJECT,
        body=html_to_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    return message


def queue_confirmation(subscription: Subscription) -> None:
    """One message per subscription created or upgraded."""
    from server.guardians.emails import may_send, send_link

    g = pending_guardian(subscription)
    if g is not None and may_send(g):
        try:
            send_link(g, reuse=True)
        except Exception:
            logger.exception("Couldn't email the guardian of player %s", g.player_id)
    if "@" not in (subscription.player.user.email or ""):
        return
    queue_emails([build_confirmation(subscription)])


def build_sponsorship_reset(player: Player, season: Season) -> EmailMultiAlternatives:
    """Sponsorship used to carry over for good; now it is granted one season
    at a time, so tell someone who had it how to ask for this one."""
    context = {
        "first_name": player.user.first_name,
        "season": season.name,
        "subscription_url": f"{settings.PUBLIC_URL}/subscription/{player.id}",
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
    player: Player, season: Season, to: User, guardianship: Guardianship | None = None
) -> EmailMultiAlternatives:
    """Asks someone to agree to this season's code of conduct: the player, or
    a minor's guardian, who gets the same link as for the waiver. A guardian's
    link stamp is set on `guardianship` but not saved: save it once the email
    is queued."""
    if to != player.user:
        g = guardianship or Guardianship.objects.filter(player=player, user=to).first()
        message = build_link(g, reuse=True, coc_request=True) if g is not None else None
        if message is not None:
            return message
    link = f"{settings.PUBLIC_URL}/code-of-conduct/{player.id}"
    one_tap = not player.is_minor and not (to.is_staff or to.is_superuser)
    if one_tap:
        link = f"{settings.PUBLIC_URL}/guardian/{tokens.mint_own(player)}"
    context = {
        "site_url": settings.PUBLIC_URL,
        "first_name": to.first_name or "there",
        "coc_url": link,
        "one_tap": one_tap,
    }
    html = render_to_string("emails/code_of_conduct_request.html", context)
    message = EmailMultiAlternatives(
        subject=CODE_OF_CONDUCT_SUBJECT,
        body=html_to_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[to.email],
    )
    message.attach_alternative(html, "text/html")
    return message
