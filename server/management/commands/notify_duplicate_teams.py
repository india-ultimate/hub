from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.duplicates.teams.emails import notify, waiting
from server.duplicates.teams.merge import label


class Command(BaseCommand):
    help = "Email team admins, once per team, about teams that look like copies of theirs."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, help="Only email this many admins.")
        parser.add_argument(
            "--dry-run", action="store_true", help="List who would be emailed, sending nothing."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["dry_run"]:
            admins = waiting()[: options["limit"]]
            for user, found in admins:
                teams = "; ".join(
                    f"{label(team)} = {', '.join(label(copy) for copy in copies)}"
                    for team, copies in found
                )
                self.stdout.write(f"{user.email}: {teams}")
            self.stdout.write(f"Would email {len(admins)} admin{'' if len(admins) == 1 else 's'}")
            return
        sent = notify(options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Queued {sent} email{'' if sent == 1 else 's'}"))
