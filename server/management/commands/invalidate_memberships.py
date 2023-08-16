from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.models import Membership, Player


class Command(BaseCommand):
    help = "Invalidate memberships whose end date has passed"

    def handle(self, *args: Any, **options: Any) -> None:
        today = now().date()
        stale_memberships = Membership.objects.filter(end_date__lt=today)
        n = stale_memberships.count()
        if n > 0:
            stale_memberships.update(is_active=False, waiver_valid=False)
            Player.objects.filter(membership__in=stale_memberships).update(sponsored=False)
            self.stdout.write(self.style.SUCCESS(f"Invalidated {n} memberships"))
        else:
            self.stdout.write(self.style.NOTICE("No outdated memberships found"))
