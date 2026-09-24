from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.duplicates.emails import notify, unnotified


class Command(BaseCommand):
    help = "Email each account in a detected duplicate cluster."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--limit", type=int, help="Only notify this many clusters.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending it.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        clusters = unnotified(options["limit"])
        if not clusters:
            self.stdout.write(self.style.NOTICE("No clusters waiting to be notified"))
            return

        if options["dry_run"]:
            self.stdout.write(f"Would notify {len(clusters)} clusters")
            return

        sent = sum(notify(cluster) for cluster in clusters)
        self.stdout.write(
            self.style.SUCCESS(f"Queued {sent} emails across {len(clusters)} clusters")
        )
