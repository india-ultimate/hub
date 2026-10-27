"""What a team merge recorded."""

from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Team, User


class TeamMerge(ExportModelOperationsMixin("team_merge"), models.Model):  # type: ignore[misc]
    """One merge of duplicate teams, and what the deleted teams held."""

    keeper = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, related_name="merges")
    merged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="team_merges"
    )
    absorbed_team_ids = models.JSONField(default=list)
    # Rows repointed at the keeper, by relation.
    moved = models.JSONField(default=dict)
    snapshot = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class TeamNotDuplicate(ExportModelOperationsMixin("team_not_duplicate"), models.Model):  # type: ignore[misc]
    """Two teams with one name that an admin said are different teams.

    Either order means the same pair. A merge repoints these like any other
    row, and drops a pair that ends up naming the kept team twice.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="not_duplicates")
    other = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="not_duplicate_of")
    decided_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="team_decisions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "other")
