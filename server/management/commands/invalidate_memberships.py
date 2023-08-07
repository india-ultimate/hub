import datetime

from django.core.management.base import BaseCommand
from server.models import Membership


class Command(BaseCommand):
    help = "Invalidate memberships whose end date has passed"

    def handle(self, *args, **options):
        today = datetime.date.today()
        active_memberships = Membership.objects.filter(end_date__lt=today, is_active=True)
        n = active_memberships.count()
        if n > 0:
            active_memberships.update(is_active=False, waiver_signed_by=None, waiver_signed_at=None)
            self.stdout.write(self.style.SUCCESS(f"Invalidated {n} memberships"))
        else:
            self.stdout.write(self.style.NOTICE("No outdated memberships found"))
