from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from server.forms.models import FormResponse

# Unpaid responses only exist for paid forms as transient payment-tracking rows
# (free-form responses are marked paid on submit). Anything still unpaid after
# this window is an abandoned checkout and can be safely removed.
ABANDONED_AFTER_HOURS = 24


class Command(BaseCommand):
    help = "Delete abandoned (unpaid) form responses older than a day"

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - timedelta(hours=ABANDONED_AFTER_HOURS)

        abandoned = FormResponse.objects.filter(is_paid=False, submitted_at__lt=cutoff)
        count = abandoned.count()
        abandoned.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} abandoned (unpaid) form response(s)")
        )
