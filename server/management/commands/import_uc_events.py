import requests
from django.core.management.base import BaseCommand
from server.models import Event

BASE_URL = "https://upai.usetopscore.com"


class Command(BaseCommand):
    help = "Import data from UC"

    def handle(self, *args, **options):
        url = "{}/api/events?per_page=200&order_by=date_desc".format(BASE_URL)
        # NOTE: The request is unauthenticated
        r = requests.get(url)
        data = r.json()
        count = data["count"]
        tournaments = data["result"]
        if len(tournaments) < count:
            print("WARNING: Need to add pagination")

        print(f"Fetched {count} events")

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

        print(f"Created {count} events")
