"""Telling team admins about likely copies of their teams, once per team."""

from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

from server.core.models import Team, User
from server.duplicates.teams.merge import label
from server.duplicates.teams.models import TeamDuplicateNotice
from server.duplicates.teams.suggest import (
    copies_of,
    merge_requested,
    normalized_name,
    same_names,
)
from server.task.helpers import queue_emails

Found = list[tuple[Team, list[Team]]]


def waiting() -> list[tuple[User, Found]]:
    """Admins with copies of their teams they haven't been told about, by admin."""
    groups = same_names()
    # Told about one copy is told about the name: they see the rest on that page.
    # By the team's name now, so a team renamed since its email still counts.
    told = {
        (user_id, normalized_name(name))
        for user_id, name in TeamDuplicateNotice.objects.values_list("user_id", "team__name")
    }
    by_admin: dict[User, Found] = {}
    teams = Team.objects.filter(pk__in=[t.pk for ts in groups.values() for t in ts])
    for team in teams.prefetch_related("admins").order_by("pk"):
        copies = copies_of(team, groups)
        if not copies or merge_requested([team, *copies]):
            continue
        key = normalized_name(team.name)
        for admin in team.admins.all():
            if "@" in admin.email and (admin.pk, key) not in told:
                told.add((admin.pk, key))
                by_admin.setdefault(admin, []).append((team, copies))
    return sorted(by_admin.items(), key=lambda item: item[0].pk)


def _detail(team: Team) -> str:
    played = team.tournaments.count()
    parts = [team.category, team.city, f"{played} tournament{'' if played == 1 else 's'}"]
    return " · ".join(part for part in parts if part)


def build(user: User, found: Found) -> EmailMultiAlternatives:
    teams = [
        {
            # Whitespace collapsed: a newline in a name would break the subject.
            "name": " ".join(team.name.split()),
            "city": team.city,
            "url": f"{settings.PUBLIC_URL}/team/{team.slug}/merge?copies="
            + ",".join(str(copy.pk) for copy in copies),
            "copies": [{"label": label(copy), "detail": _detail(copy)} for copy in copies],
        }
        for team, copies in found
    ]
    subject = (
        f"{teams[0]['name']} may have been added twice on India Ultimate Hub"
        if len(teams) == 1
        else f"{len(teams)} of your teams may have been added twice on India Ultimate Hub"
    )
    context: dict[str, Any] = {"first_name": user.first_name, "teams": teams, "subject": subject}
    message = EmailMultiAlternatives(
        subject=subject,
        # Written out, not stripped from the HTML: stripping would drop the links.
        body=render_to_string("duplicate_teams_email.txt", context),
        from_email=settings.EMAIL_HOST_USER,
        to=[user.email],
    )
    message.attach_alternative(render_to_string("duplicate_teams_email.html", context), "text/html")
    return message


def notify(limit: int | None = None) -> int:
    """Queue one email per admin waiting, and remember who was told. Returns how many."""
    sent = 0
    for user, candidates in waiting()[:limit]:
        with transaction.atomic():
            # Held so two runs at once cannot both email this admin: the second
            # waits here, then finds the first one's notices.
            User.objects.select_for_update().filter(pk=user.pk).first()
            told = {
                normalized_name(name)
                for name in TeamDuplicateNotice.objects.filter(user=user).values_list(
                    "team__name", flat=True
                )
            }
            found = [
                (team, copies)
                for team, copies in candidates
                if normalized_name(team.name) not in told
            ]
            if not found:
                continue
            TeamDuplicateNotice.objects.bulk_create(
                [TeamDuplicateNotice(user=user, team=team) for team, _ in found]
            )
            queue_emails([build(user, found)])
            sent += 1
    return sent
