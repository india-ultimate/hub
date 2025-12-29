from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player


class PlayerWrapped(ExportModelOperationsMixin("player_wrapped"), models.Model):  # type: ignore[misc]
    """
    Year-end wrapped statistics for a player.
    Stores comprehensive statistics for a player for a specific year.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="wrapped_data")
    year = models.PositiveIntegerField(
        help_text="The year for which this wrapped data is generated"
    )

    # Basic statistics
    tournaments_played = models.PositiveIntegerField(
        default=0, help_text="Total number of tournaments played in this year"
    )
    total_games = models.PositiveIntegerField(
        default=0, help_text="Total number of games played in this year"
    )
    total_scores = models.PositiveIntegerField(
        default=0, help_text="Total number of scores in this year"
    )
    total_assists = models.PositiveIntegerField(
        default=0, help_text="Total number of assists in this year"
    )
    total_blocks = models.PositiveIntegerField(
        default=0, help_text="Total number of blocks in this year"
    )

    # Match awards
    match_mvps = models.PositiveIntegerField(
        default=0, help_text="Total number of Match MVP awards received"
    )
    match_msps = models.PositiveIntegerField(
        default=0, help_text="Total number of Match MSP awards received"
    )

    # Streaks
    continuous_streak_scored_or_assisted = models.PositiveIntegerField(
        default=0,
        help_text="Longest continuous streak of games where player either scored or assisted",
    )

    # Tournament bests
    # Format: {"tournament_name": str, "tournament_id": int, "count": int}
    most_scores_in_tournament = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tournament with most scores: {tournament_name, tournament_id, count}",
    )
    most_assists_in_tournament = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tournament with most assists: {tournament_name, tournament_id, count}",
    )
    most_blocks_in_tournament = models.JSONField(
        default=dict,
        blank=True,
        help_text="Tournament with most blocks: {tournament_name, tournament_id, count}",
    )

    # Teams played for
    # Format: [{"team_name": str, "team_id": int, "tournament_count": int}, ...]
    teams_played_for = models.JSONField(
        default=list,
        blank=True,
        help_text="List of teams played for with tournament counts: [{team_name, team_id, tournament_count}, ...]",
    )

    # Teammate statistics
    # Format: [{"player_name": str, "player_id": int, "count": int}, ...] (top 5)
    top_teammates_i_assisted = models.JSONField(
        default=list,
        blank=True,
        help_text="Top 5 teammates I assisted: [{player_name, player_id, count}, ...]",
    )
    top_teammates_who_assisted_me = models.JSONField(
        default=list,
        blank=True,
        help_text="Top 5 teammates who assisted me: [{player_name, player_id, count}, ...]",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("player", "year")
        ordering = ["-year", "player"]
        indexes = [
            models.Index(fields=["player", "year"]),
            models.Index(fields=["year"]),
        ]

    def __str__(self) -> str:
        return f"{self.player.user.get_full_name()} - {self.year} Wrapped"
