import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import IntegrityError

from server.core.models import Player, Team, User
from server.membership.models import Membership
from server.tournament.models import Event, Registration, Tournament
from server.tournament.utils import can_register_player_to_series_event


class Command(BaseCommand):
    help = "Add to event roster from CSV file with player details"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_file", type=Path, help="Path to the CSV file")
        parser.add_argument("--team-id", "-t", help="Team ID")
        parser.add_argument("--event-id", "-s", help="Event ID")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            event = Event.objects.get(id=options["event_id"])
            team = Team.objects.get(id=options["team_id"])
            tournament = Tournament.objects.get(event=event)
        except (Event.DoesNotExist, Team.DoesNotExist, Tournament.DoesNotExist):
            self.stderr.write(self.style.ERROR("Event / Team / Tournament does not exist"))
            return

        if team not in tournament.teams.all():
            self.stderr.write(
                self.style.ERROR(f"{team.name} is not registered for ${event.title} !")
            )
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

                if event.series:
                    can_register, error = can_register_player_to_series_event(
                        event=event, team=team, player=player
                    )
                    if not can_register and error:
                        self.stderr.write(self.style.ERROR(f"Error: {error}, player: {email}"))
                        continue

                if event.is_membership_needed:
                    try:
                        membership = player.membership
                    except Membership.DoesNotExist:
                        self.stderr.write(self.style.ERROR(f"Membership not found: {email}"))
                        continue

                    if not membership.is_active:
                        self.stderr.write(self.style.ERROR(f"Membership not active: {email}"))
                        continue

                    if not membership.waiver_valid:
                        self.stderr.write(self.style.ERROR(f"Waiver not valid: {email}"))
                        continue

                registration = Registration(
                    event=event,
                    team=team,
                    player=player,
                )
                try:
                    registration.save()
                except IntegrityError:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error: Player already added to another team for this event, player: {email}"
                        )
                    )
                    continue
