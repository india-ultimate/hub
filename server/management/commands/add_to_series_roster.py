import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Player, Team, User
from server.series.models import Series
from server.series.utils import register_player


class Command(BaseCommand):
    help = "Add to series roster from CSV file with player details"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument("--team-id", "-t", help="Team ID")
        parser.add_argument("--series-id", "-s", help="Series ID")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            series = Series.objects.get(id=options["series_id"])
            team = Team.objects.get(id=options["team_id"])
        except (Series.DoesNotExist, Team.DoesNotExist):
            self.stderr.write(self.style.ERROR("Series / Team does not exist"))
            return

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

                series_registration, error = register_player(
                    series=series, team=team, player=player
                )
                if error:
                    self.stderr.write(self.style.ERROR(f"Error: {error}, player: {email}"))
                    continue

                if series_registration is None:
                    self.stderr.write(
                        self.style.ERROR(f"Error: Couldn't register player, player: {email}")
                    )
                    continue
