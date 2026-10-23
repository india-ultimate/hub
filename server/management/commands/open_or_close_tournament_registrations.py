from typing import Any

from django.core.management.base import BaseCommand

from server.tournament.models import Tournament
from server.utils import today


class Command(BaseCommand):
    help = "List every draft tournament whose team registration has opened"

    def handle(self, *args: Any, **options: Any) -> None:
        # On or before today, so dates edited after a run, or a missed run, still list it.
        opened = Tournament.objects.filter(
            event__team_registration_start_date__lte=today(), status=Tournament.Status.DRAFT
        )
        for tournament in opened.select_related("event"):
            self.stdout.write(f"Listing {tournament.event.title} ({tournament.pk})")
        opened.update(status=Tournament.Status.SCHEDULING)
