from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, Team, User
from server.season.models import Season
from server.utils import default_invitation_expiry_date, slugify_max


class Series(ExportModelOperationsMixin("series"), models.Model):  # type: ignore[misc]
    class Type(models.TextChoices):
        MIXED = "MXD", _("Mixed")
        OPENS = "OPN", _("Opens")
        WOMENS = "WMN", _("Womens")

    class Category(models.TextChoices):
        CLUB = "Club", _("Club")
        COLLEGE = "College", _("College")
        SCHOOL = "School", _("School")
        STATE = "State", _("State")

    start_date = models.DateField()
    end_date = models.DateField()
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, null=True, blank=True, db_index=True)
    type = models.CharField(max_length=3, choices=Type.choices)
    category = models.CharField(max_length=7, choices=Category.choices)
    series_roster_max_players = models.PositiveSmallIntegerField()
    event_min_players_male = models.PositiveSmallIntegerField()
    event_min_players_female = models.PositiveSmallIntegerField()
    event_max_players_male = models.PositiveSmallIntegerField()
    event_max_players_female = models.PositiveSmallIntegerField()
    player_transfer_window_start_date = models.DateField(blank=True, null=True)
    player_transfer_window_end_date = models.DateField(blank=True, null=True)
    season = models.ForeignKey(
        Season, on_delete=models.SET_NULL, null=True, blank=True, related_name="series"
    )
    teams = models.ManyToManyField(Team, related_name="series", blank=True)

    class Meta:
        unique_together = ["season", "name"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = self.get_slug()

        return super().save(*args, **kwargs)

    def get_slug(self) -> str:
        slug = slugify_max(self.name, max_length=95)
        unique_slug = slug

        number = 1
        while Series.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{unique_slug}-{number}"
            number += 1

        return unique_slug


class SeriesRegistration(ExportModelOperationsMixin("series_registration"), models.Model):  # type: ignore[misc]
    series = models.ForeignKey(Series, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)


class SeriesRosterInvitation(ExportModelOperationsMixin("series_roster_invitation"), models.Model):  # type: ignore[misc]
    class Status(models.TextChoices):
        PENDING = "Pending", _("Pending")
        ACCEPTED = "Accepted", _("Accepted")
        DECLINED = "Declined", _("Declined")
        EXPIRED = "Expired", _("Expired")
        REVOKED = "Revoked", _("Revoked")

    series = models.ForeignKey(Series, on_delete=models.CASCADE)
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="series_invitations_sent"
    )
    to_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="series_invitations_received"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    expires_on = models.DateField(default=default_invitation_expiry_date)
    created_at = models.DateTimeField(auto_now_add=True)
    rsvp_date = models.DateField(blank=True, null=True)
