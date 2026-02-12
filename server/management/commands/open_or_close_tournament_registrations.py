from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.tournament.models import Tournament


class Command(BaseCommand):
    help = (
        "Check if registrations are open or closed today, and update tournament status accordingly"
    )

    def handle(self, *args: Any, **options: Any) -> None:
        today = now().date()

        team_registrations_open_today = Tournament.objects.filter(
            event__team_registration_start_date__exact=today, status=Tournament.Status.DRAFT
        )

        if team_registrations_open_today.count() > 0:
            team_registrations_open_today.update(status=Tournament.Status.SCHEDULING)
