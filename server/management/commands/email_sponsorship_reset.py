"""Tell people whose sponsorship no longer carries over that they can ask again."""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Player
from server.membership.emails import SPONSORSHIP_RESET_SUBJECT, build_sponsorship_reset
from server.membership.models import SponsorshipGrant
from server.season.models import Season
from server.task.helpers import queue_emails
from server.task.models import Task


def already_queued() -> set[str]:
    """Addresses this email has already been queued for.

    ponytail: reads the task queue, and cleanup_old_tasks deletes finished
    tasks after 7 days, so a re-run more than a week later would write to
    everyone again. Add a sent-at record if this is ever run on a schedule.
    """
    tasks = Task.objects.filter(
        type=Task.TaskType.SEND_EMAIL, data__subject=SPONSORSHIP_RESET_SUBJECT
    )
    return {address for task in tasks for address in task.data.get("to", [])}


class Command(BaseCommand):
    help = (
        "Email everyone who was sponsored but has no grant for the current season. "
        "Run with --dry-run first: the emails cannot be unsent."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List exactly who would be written to, and send nothing.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        season = Season.current()
        if season is None:
            self.stderr.write(self.style.ERROR("No current season."))
            return

        granted = set(
            SponsorshipGrant.objects.filter(season=season).values_list("player_id", flat=True)
        )
        sent = already_queued()
        losing = [
            player
            for player in Player.objects.filter(sponsored=True)
            .select_related("user")
            .order_by("id")
            if player.id not in granted
            and "@" in (player.user.email or "")
            and player.user.email not in sent
        ]

        if options["dry_run"]:
            self.stdout.write(f"Would write to {len(losing)} people about {season.name}:")
            for player in losing:
                self.stdout.write(f"  {player.id}\t{player.user.email}")
            return

        if not losing:
            self.stdout.write(self.style.NOTICE("Nobody to write to."))
            return

        queue_emails([build_sponsorship_reset(player, season) for player in losing])
        self.stdout.write(self.style.SUCCESS(f"Queued {len(losing)} emails"))
