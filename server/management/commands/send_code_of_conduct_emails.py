"""Ask everyone with this season's subscription who hasn't agreed to the code
of conduct to do so. Safe to run again: it only reaches people still missing it."""

import datetime
from typing import Any

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction

from server.core.models import Guardianship, User
from server.season.models import Season
from server.subscription.emails import build_code_of_conduct_request
from server.subscription.models import Subscription
from server.task.helpers import queue_emails


class Command(BaseCommand):
    help = "Email current members who haven't agreed to the code of conduct"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="List them; send nothing")

    def handle(self, *args: Any, **options: Any) -> None:
        season = Season.current()
        if season is None:
            self.stderr.write(self.style.ERROR("No current season"))
            return
        missing = Subscription.objects.filter(
            season=season, is_active=True, coc_agreed=False
        ).select_related("player__user")
        messages: list[EmailMultiAlternatives] = []
        skipped: list[str] = []
        stamped: list[tuple[Guardianship, datetime.datetime | None]] = []
        for sub in missing:
            player = sub.player
            name = player.user.get_full_name()
            to: User | None = player.user
            g: Guardianship | None = None
            if player.is_minor:
                try:
                    g = player.guardianship
                    to = g.user
                except Guardianship.DoesNotExist:
                    to = None
            if to is None or "@" not in (to.email or ""):
                skipped.append(name)
                continue
            who = name if to == player.user else f"guardian of {name}"
            self.stdout.write(f"{to.email}  ({who})")
            before = g.link_sent_at if g is not None else None
            messages.append(build_code_of_conduct_request(player, season, to, g))
            if g is not None and g.link_sent_at != before:
                stamped.append((g, before))
        self.stdout.write(f"{len(messages)} to send")
        if skipped:
            self.stdout.write(f"Skipped, no usable email: {', '.join(skipped)}")
        if not options["dry_run"] and messages:
            with transaction.atomic():
                queue_emails(messages)
                for g, before in stamped:
                    Guardianship.objects.filter(pk=g.pk, link_sent_at=before).update(
                        link_sent_at=g.link_sent_at
                    )
            self.stdout.write(self.style.SUCCESS(f"Queued {len(messages)} emails"))
