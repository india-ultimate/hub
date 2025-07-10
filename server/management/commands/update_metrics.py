"""
Management command to update business metrics for Fly.io monitoring.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from datetime import timedelta

from server.core.models import Team, Player
from server.tournament.models import Tournament
from server.metrics import (
    total_teams_gauge,
    total_players_gauge,
    active_tournaments_gauge,
    database_connections_gauge,
)


class Command(BaseCommand):
    help = 'Update business metrics for Fly.io monitoring'

    def handle(self, *args, **options):
        """Update all business metrics."""
        self.stdout.write('Updating business metrics...')
        
        try:
            # Update team count
            team_count = Team.objects.count()
            total_teams_gauge.set(team_count)
            self.stdout.write(f'Updated team count: {team_count}')
            
            # Update player count
            player_count = Player.objects.count()
            total_players_gauge.set(player_count)
            self.stdout.write(f'Updated player count: {player_count}')
            
            # Update active tournaments (tournaments in the last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            active_tournament_count = Tournament.objects.filter(
                created_at__gte=thirty_days_ago
            ).count()
            active_tournaments_gauge.set(active_tournament_count)
            self.stdout.write(f'Updated active tournaments: {active_tournament_count}')
            
            # Update database connections
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                connection_count = cursor.fetchone()[0]
                database_connections_gauge.set(connection_count)
                self.stdout.write(f'Updated database connections: {connection_count}')
            
            self.stdout.write(
                self.style.SUCCESS('Successfully updated all business metrics')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating metrics: {e}')
            )