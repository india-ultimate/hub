import requests
from django.core.management.base import BaseCommand
from server.models import Event

BASE_URL = "https://upai.usetopscore.com"


class Command(BaseCommand):
    help = "Import data from UC"

    def add_arguments(self, parser):
        parser.add_argument(
            "-n",
            "--num-events",
            default=200,
            type=int,
            help="Number of events to sync.",
        )

    def handle(self, *args, **options):
        n = options["num_events"]
        url = f"{BASE_URL}/api/events?per_page={n}&order_by=date_desc"
        # NOTE: The request is unauthenticated
        r = requests.get(url)
        data = r.json()
        count = min(data["count"], n)
        tournaments = data["result"]
        if len(tournaments) < count:
            print("WARNING: Need to add pagination")

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
