"""
Email functions for announcements
"""

import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from server.announcements.models import Announcement
from server.core.models import User
from server.membership.models import Membership
from server.task.helpers import queue_emails
from server.task.models import Task

CONTENT_PREVIEW_LENGTH = 300


def send_announcement_to_all_users(announcement: Announcement) -> list[Task]:
    """
    Queue announcement emails to users with player profiles

    :param announcement: Announcement instance
    :return: List of created Task objects
    """
    users = User.objects.filter(email__isnull=False, player_profile__isnull=False).exclude(email="")
    recipients = list(users.values_list("email", flat=True))
    return _queue_announcement_emails(announcement, recipients)


def send_announcement_to_members(announcement: Announcement) -> list[Task]:
    """
    Queue announcement emails to users with active memberships

    :param announcement: Announcement instance
    :return: List of created Task objects
    """
    active_memberships = Membership.objects.filter(is_active=True).select_related("player__user")
    recipients = list(active_memberships.values_list("player__user__email", flat=True).distinct())
    return _queue_announcement_emails(announcement, recipients)


def send_announcement_to_email(announcement: Announcement, email: str) -> list[Task]:
    """
    Queue announcement email to a single email address

    :param announcement: Announcement instance
    :param email: Email address
    :return: List of created Task objects (single task)
    """
    return _queue_announcement_emails(announcement, [email])


def _normalize_email(email: str) -> str:
    """
    Normalize email by removing plus addressing (user+tag@domain.com -> user@domain.com)

    :param email: Email address
    :return: Normalized email address
    """
    if "+" in email and "@" in email:
        local_part, domain = email.rsplit("@", 1)
        if "+" in local_part:
            local_part = local_part.split("+")[0]
        return f"{local_part}@{domain}"
    return email


def _queue_announcement_emails(announcement: Announcement, recipients: list[str]) -> list[Task]:
    """
    Create and queue announcement email tasks

    :param announcement: Announcement instance
    :param recipients: List of recipient email addresses
    :return: List of created Task objects
    """
    if not recipients:
        return []

    # Deduplicate recipients by normalizing emails (handle plus addressing)
    seen_normalized: dict[str, str] = {}
    unique_recipients = []

    for email in recipients:
        normalized = _normalize_email(email.lower())
        if normalized not in seen_normalized:
            seen_normalized[normalized] = email
            unique_recipients.append(email)

    site_url = getattr(settings, "SITE_URL", "https://indiaultimate.org")
    announcement_url = f"{site_url}/announcements/{announcement.slug}"

    # Get content preview
    content_preview = announcement.content[:CONTENT_PREVIEW_LENGTH]
    if len(announcement.content) > CONTENT_PREVIEW_LENGTH:
        content_preview += "..."

    # Strip HTML tags for plain text version
    plain_text_content = re.sub(r"<[^>]+>", "", announcement.content)
    plain_text_content = re.sub(r"\s+", " ", plain_text_content).strip()
    plain_text_preview = plain_text_content[:CONTENT_PREVIEW_LENGTH]
    if len(plain_text_content) > CONTENT_PREVIEW_LENGTH:
        plain_text_preview += "..."

    messages: list[EmailMultiAlternatives] = []
    for recipient_email in unique_recipients:
        html_content = render_to_string(
            "emails/announcement_notification.html",
            {
                "announcement": announcement,
                "content_preview": content_preview,
                "site_url": site_url,
                "announcement_url": announcement_url,
            },
        )

        plain_content = f"""
New Announcement: {announcement.title}

Category: {announcement.get_type_display()}

{plain_text_preview}

Read the full announcement at: {announcement_url}

---
Posted by: {announcement.author.get_full_name()}
India Ultimate Hub
"""

        msg = EmailMultiAlternatives(
            subject=f"📢 {announcement.title}",
            body=plain_content,
            from_email=None,
            to=[recipient_email],
        )
        msg.attach_alternative(html_content, "text/html")
        messages.append(msg)

    return queue_emails(messages)
