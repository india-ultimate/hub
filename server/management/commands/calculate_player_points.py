from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from server.core.models import Team
from server.tournament.models import Event, Registration, Tournament


class Command(BaseCommand):
    help = "Calculate player points based on tournament result and store in registrations"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--force", "-f", default=False, help="Force calculate")

    def get_base_points(self, tier: int) -> int:
        """Get base points based on event tier"""
        tier_points = {
            1: 80,  # Tier 1 events get 80 base points
            2: 60,  # Tier 2 events get 60 base points
            3: 40,  # Tier 3 events get 40 base points
            4: 20,  # Tier 4 events get 20 base points (default)
        }
        return tier_points.get(tier, 20)  # Default to 20 if tier not found

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

            # Get base points based on event tier
            base_points = self.get_base_points(event.tier)

            # Calculate points for each team based on their ranking
            for rank, team_id in current_seeding.items():
                points_per_position = float((100 - base_points) / (total_teams - 1))

                points: float | None = round(
                    base_points + ((total_teams - int(rank)) * points_per_position), 1
                )

                if event.tier == 0:
                    points = None

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
