"""Players a team admin has added for a tournament but not yet paid for."""

from django.db import models

from server.core.models import Player, Team, User
from server.tournament.models import Event


class RosterEntry(models.Model):
    """One unpaid line. Its state is computed, never stored: see state.py.

    Paying turns it into a Registration (the roster of record) and deletes it.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="roster_entries")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="roster_entries")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="roster_entries")
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True, related_name="roster_entries_added"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    # Set while the entry is in an open checkout, so two admins can't pay for
    # the same person. Released lazily after 20 minutes unpaid.
    held_by_order = models.ForeignKey(
        "server.RazorpayTransaction",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="held_entries",
    )

    class Meta:
        unique_together = ("event", "team", "player")
        ordering = ["added_at", "id"]

    def __str__(self) -> str:
        return f"{self.player} for {self.team} at {self.event}"
