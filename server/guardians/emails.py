"""The email that asks a guardian to sign a ward's waiver."""

import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.timezone import now

from server.core.models import Guardianship, Player, User
from server.guardians import tokens
from server.subscription.models import Subscription
from server.task.helpers import html_to_text, queue_emails

RESEND_AFTER = datetime.timedelta(minutes=10)
TOO_SOON = "A link was just sent. You can send another in 10 minutes."


def _pending(sub: Subscription | None) -> tuple[bool, bool]:
    return sub is None or not sub.waiver_valid, sub is None or not sub.coc_agreed


def to_sign(sub: Subscription | None) -> str:
    """What is still unsigned on a subscription, in words."""
    waiver, coc = _pending(sub)
    return " and ".join(item for item, due in (("waiver", waiver), ("code of conduct", coc)) if due)


def to_do(sub: Subscription | None, owner: str) -> str:
    """What someone has to do, as a verb phrase: sign the waiver, agree to the code."""
    waiver, coc = _pending(sub)
    the = "the" if owner == "your" else owner
    steps = []
    if waiver:
        steps.append(f"sign {owner} waiver")
    if coc:
        steps.append(f"agree to {the} code of conduct")
    return " and ".join(steps)


def title_for(sub: Subscription | None, first: str) -> str:
    waiver, coc = _pending(sub)
    if waiver and coc:
        return f"Please sign {first}'s waiver and agree to the code of conduct"
    if waiver:
        return f"Please sign {first}'s waiver"
    return f"Please agree to {first}'s code of conduct"


def may_send(g: Guardianship) -> bool:
    return g.link_sent_at is None or now() - g.link_sent_at > RESEND_AFTER


def build_link(
    g: Guardianship, *, reuse: bool = False, by: User | None = None, coc_request: bool = False
) -> EmailMultiAlternatives | None:
    """The email with a guardian's link; None if they have no address.

    A new stamp retires every earlier link. With `reuse`, a stamp whose link
    is still within MAX_AGE is kept, so the link already in the inbox keeps
    working. The caller saves the stamp.
    """
    if "@" not in (g.user.email or ""):
        return None
    stale = g.link_sent_at is None or now() - g.link_sent_at > tokens.MAX_AGE
    if stale or not reuse:
        g.link_sent_at = now()
    player = g.player
    ward_first = player.user.first_name
    sub = player.current_subscription
    waiver, coc = _pending(sub)
    title = title_for(sub, ward_first)
    context = {
        "site_url": settings.PUBLIC_URL,
        "first_name": g.user.first_name or "there",
        "ward_first_name": ward_first,
        "by_is_ward": by is None or by.pk == player.user_id,
        "by_first_name": by.first_name or by.get_username() if by else ward_first,
        "title": title,
        "to_do": to_do(sub, "their"),
        "button": "Read and agree" if coc and not waiver else "Read and sign",
        "long": waiver and coc,
        "coc_request": coc_request,
        "coc_only": coc and not waiver,
        "resend_label": "Resend code of conduct link" if not waiver else "Resend link",
        "link_url": f"{settings.PUBLIC_URL}/guardian/{tokens.mint(g)}",
        "has_subscription": sub is not None,
    }
    html = render_to_string("emails/guardian_link.html", context)
    message = EmailMultiAlternatives(
        subject=title,
        body=html_to_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[g.user.email],
    )
    message.attach_alternative(html, "text/html")
    return message


def send_link(g: Guardianship, *, reuse: bool = False, by: User | None = None) -> bool:
    """Email a link; False if the guardian has no address to send to."""
    message = build_link(g, reuse=reuse, by=by)
    if message is None:
        return False
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
            "site_url": settings.PUBLIC_URL,
            "first_name": old.first_name or "there",
            "by_name": by.get_full_name() or by.get_username(),
            "by_is_ward": by.pk == g.player.user_id,
            "ward_first_name": ward_first,
            "new_name": g.user.get_full_name() or g.user.get_username(),
        },
    )
    message = EmailMultiAlternatives(
        subject=f"{ward_first}'s guardian was changed",
        body=html_to_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[old.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])


def send_waiver_reminder(player: Player, by: User, team_name: str) -> bool:
    """Ask an adult player to sign their own waiver, naming who asked. The
    link signs them in."""
    if "@" not in (player.user.email or ""):
        return False
    one_tap = not (player.user.is_staff or player.user.is_superuser)
    waiver_url = (
        f"{settings.PUBLIC_URL}/guardian/{tokens.mint_own(player)}"
        if one_tap
        else f"{settings.PUBLIC_URL}/waiver/{player.id}"
    )
    html = render_to_string(
        "emails/waiver_reminder.html",
        {
            "site_url": settings.PUBLIC_URL,
            "first_name": player.user.first_name or "there",
            "by_name": by.get_full_name() or by.get_username(),
            "team_name": team_name,
            "waiver_url": waiver_url,
            "one_tap": one_tap,
        },
    )
    message = EmailMultiAlternatives(
        subject="Please sign your India Ultimate waiver",
        body=html_to_text(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[player.user.email],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])
    return True
