from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand

from server.receipts.backfill import backfill


class Command(BaseCommand):
    help = (
        "Issue receipts and refund notes for paid subscription orders that have none. "
        "Migration 0159 did this once; an order the old release captured after that "
        "snapshot never gets one from the callback, the webhook or the nightly sync, "
        "which all treat a settled order as done. Idempotent, and it emails nobody."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        receipts, notes = backfill(apps)
        self.stdout.write(
            self.style.SUCCESS(f"Issued {receipts} receipts and {notes} refund notes.")
        )
