from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.models import Event
from server.top_score_utils import TopScoreClient


class Command(BaseCommand):
    help = "Import events from Ultimate Central"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "-n",
            "--num-events",
            default=200,
            type=int,
            help="Number of events to sync.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        client = TopScoreClient()
        tournaments = client.get_events(options["num_events"])
        if tournaments is None:
            self.stdout.write(self.style.ERROR("Failed to fetch events"))
            return

        count = len(tournaments)
        self.stdout.write(self.style.SUCCESS(f"Fetched {count} events"))

        # Create events
        count = 0
        for tournament in tournaments:
            _, created = Event.objects.get_or_create(
                ultimate_central_id=tournament["id"],
                defaults={
                    "title": tournament["name"],
                    "start_date": tournament["start"],
                    "end_date": tournament["end"],
                    "ultimate_central_slug": tournament["slug"],
                },
            )
            if created:
                count += 1

        style = self.style.SUCCESS if count > 0 else self.style.NOTICE
        self.stdout.write(style(f"Created {count} events"))
