import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils.timezone import now

from server.core.models import Player, User
from server.season.models import Season
from server.subscription import catalog
from server.subscription.models import Subscription
from server.subscription.numbers import assign_number


class Command(BaseCommand):
    # Only for people who signed the waiver and agreed to the code of conduct
    # offline: both are marked done for everyone in the sheet.
    help = (
        "Activate subscriptions from CSV file with player details. Marks the waiver "
        "signed and the code of conduct agreed, so use it only for people who did both "
        "offline."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument(
            "--tier",
            default=catalog.REGULAR,
            help="Tier slug to give these subscriptions (default: regular)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Season.current(), not the first row whose end_date is in the future:
        # that ordering was undefined, so which season people got depended on
        # whatever order the database happened to return.
        season = Season.current()

        if season is None:
            self.stderr.write(self.style.ERROR("No Season found"))
            return

        plan = catalog.plan_for(season, options["tier"])
        if plan is None:
            self.stderr.write(self.style.ERROR(f"No '{options['tier']}' plan for {season.name}"))
            return

        subscription_defaults = {
            "start_date": season.start_date,
            "end_date": season.end_date,
            "event": None,
            "plan": plan,
            "is_active": True,
            "waiver_valid": True,
        }

        csv_file = options["csv_file"]

        with open(csv_file) as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Process each row of the CSV file
                email = row["email"].strip().lower()

                try:
                    user = User.objects.get(username=email)
                    player = Player.objects.get(user=user)
                except (User.DoesNotExist, Player.DoesNotExist):
                    self.stderr.write(self.style.ERROR(f"Player not found: {email}"))
                    continue

                subscription, created = Subscription.objects.get_or_create(
                    player=player, season=season, defaults=subscription_defaults
                )
                if not created:
                    for key, value in subscription_defaults.items():
                        setattr(subscription, key, value)
                    subscription.save()
                if not subscription.coc_agreed:
                    # Agreed offline: a date, but no one who agreed on the Hub.
                    # An agreement already made on the Hub is left as it is.
                    subscription.coc_agreed = True
                    subscription.coc_agreed_at = now()
                    subscription.save(update_fields=["coc_agreed", "coc_agreed_at"])

                assign_number(player, season)
