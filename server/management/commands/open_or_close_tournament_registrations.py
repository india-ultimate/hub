from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.models import Tournament


class Command(BaseCommand):
    help = (
        "Check if registrations are open or closed today, and update tournament status accordingly"
    )

    def handle(self, *args: Any, **options: Any) -> None:
        today = now().date()

        registrations_open_today = Tournament.objects.filter(
            event__registration_start_date__exact=today, status=Tournament.Status.DRAFT
        )
        registrations_closed_today = Tournament.objects.filter(
            event__registration_end_date__lt=today, status=Tournament.Status.REGISTERING
        )

        if registrations_open_today.count() > 0:
            registrations_open_today.update(status=Tournament.Status.REGISTERING)

        if registrations_closed_today.count() > 0:
            registrations_closed_today.update(status=Tournament.Status.SCHEDULING)
