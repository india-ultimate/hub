"""Delete college ID images 30 days after the card expires; keep the row."""

import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import CollegeId
from server.utils import today

GRACE = datetime.timedelta(days=30)


class Command(BaseCommand):
    help = "Delete college ID images 30 days after the card expires"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", action="store_true", help="List them; delete nothing")

    def handle(self, *args: Any, **options: Any) -> None:
        cards = CollegeId.objects.filter(expiry__lt=today() - GRACE, images_removed_at__isnull=True)
        self.stdout.write(f"{cards.count()} to clear")
        if options["dry_run"]:
            return
        failed = 0
        for card in cards:
            try:
                for image in (card.card_front, card.card_back):
                    if image:
                        image.storage.delete(image.name)
            except Exception as error:  # left as it is; tried again tomorrow
                failed += 1
                self.stderr.write(f"College ID {card.pk}: {error}")
                continue
            card.card_front = card.card_back = ""
            card.images_removed_at = today()
            card.save(update_fields=["card_front", "card_back", "images_removed_at"])
        if failed:
            self.stdout.write(f"{failed} failed")
