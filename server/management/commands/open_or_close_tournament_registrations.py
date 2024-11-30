from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.tournament.models import Registration, Tournament


class Command(BaseCommand):
    help = "Check if registrations are open or closed today, and update tournament status accordingly. Also update registration's player teams on day of tournament"

    def handle(self, *args: Any, **options: Any) -> None:
        today = now().date()

        team_registrations_open_today = Tournament.objects.filter(
            event__team_registration_start_date__exact=today, status=Tournament.Status.DRAFT
        )
        team_registrations_closed_today = Tournament.objects.filter(
            event__team_registration_end_date__lt=today, status=Tournament.Status.REGISTERING
        )

        if team_registrations_open_today.count() > 0:
            team_registrations_open_today.update(status=Tournament.Status.REGISTERING)

        if team_registrations_closed_today.count() > 0:
            team_registrations_closed_today.update(status=Tournament.Status.SCHEDULING)

        tournaments_that_starts_today = Tournament.objects.filter(
            event__start_date__exact=today, status=Tournament.Status.LIVE
        )

        for tournament in tournaments_that_starts_today:
            registrations = Registration.objects.filter(event=tournament.event)

            for reg in registrations:
                reg.player.teams.add(reg.team)
