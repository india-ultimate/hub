from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Team
from server.tournament.models import Event, Registration, Tournament


class Command(BaseCommand):
    help = "Calculate player points based on tournament result and store in registrations"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--force", "-f", default=False, help="Force calculate")

    def handle(self, *args: Any, **options: Any) -> None:
        force_calculate = options["force"]

        events = Event.objects.all()

        for event in events:
            regs = Registration.objects.filter(event=event)

            # Get tournament if exists
            try:
                tournament = Tournament.objects.get(event=event)
            except Tournament.DoesNotExist:
                continue

            # Skip if no registrations or tournament is not completed yet
            if regs.count() == 0 or tournament.status != Tournament.Status.COMPLETED:
                continue

            current_seeding = tournament.current_seeding

            # Total number of teams
            total_teams = len(current_seeding)

            # Calculate points for each team based on their ranking
            for rank, team_id in current_seeding.items():
                base_points = 20
                points_per_position = float(80 / (total_teams - 1))

                points = round(base_points + ((total_teams - int(rank)) * points_per_position), 1)

                team = Team.objects.get(id=team_id)
                team_regs = regs.filter(team=team)

                for reg in team_regs:
                    if reg.points is None or force_calculate:
                        reg.points = points
                        reg.save()

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully calculated {reg.player.user.get_full_name()} for {reg.team.name} in {reg.event.title}"
                            )
                        )
