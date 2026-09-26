import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Player, User
from server.membership import catalog
from server.membership.models import Membership
from server.membership.numbers import assign_number
from server.season.models import Season


class Command(BaseCommand):
    help = "Activate memberships from CSV file with player details"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument(
            "--tier",
            default=catalog.REGULAR,
            help="Tier slug to give these memberships (default: regular)",
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

        membership_defaults = {
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

                membership, created = Membership.objects.get_or_create(
                    player=player, season=season, defaults=membership_defaults
                )
                if not created:
                    for key, value in membership_defaults.items():
                        setattr(membership, key, value)
                    membership.save()

                assign_number(player, season)
