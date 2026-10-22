from typing import Any

from django.core.management.base import BaseCommand

from server.accreditation.models import Accreditation
from server.utils import today


class Command(BaseCommand):
    help = "Invalidate accreditations whose validity end date has passed"

    def handle(self, *args: Any, **options: Any) -> None:
        stale_accreditations = Accreditation.objects.filter(expiry_date__lt=today())
        n = stale_accreditations.count()
        if n > 0:
            stale_accreditations.update(is_valid=False)
            self.stdout.write(self.style.SUCCESS(f"Invalidated {n} accreditations"))
        else:
            self.stdout.write(self.style.NOTICE("No outdated accreditations found"))

        valid_accreditations = Accreditation.objects.filter(expiry_date__gte=today())
        n = valid_accreditations.count()
        if n > 0:
            valid_accreditations.update(is_valid=True)
            self.stdout.write(self.style.SUCCESS(f"Validated {n} accreditations"))
        else:
            self.stdout.write(self.style.NOTICE("No valid accreditations found"))
