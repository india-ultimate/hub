from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from server.subscription.models import Subscription


class Command(BaseCommand):
    help = "Invalidate subscriptions whose end date has passed"

    def handle(self, *args: Any, **options: Any) -> None:
        today = now().date()
        stale_subscriptions = Subscription.objects.filter(end_date__lt=today)
        n = stale_subscriptions.count()
        if n > 0:
            stale_subscriptions.update(is_active=False, waiver_valid=False)
            self.stdout.write(self.style.SUCCESS(f"Invalidated {n} subscriptions"))
        else:
            self.stdout.write(self.style.NOTICE("No outdated subscriptions found"))
