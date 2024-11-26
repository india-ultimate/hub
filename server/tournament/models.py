from typing import Any

from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.core.models import Player, Team, UCPerson, User
from server.series.models import Series, SeriesRegistration
from server.utils import default_invitation_expiry_date, slugify_max


class Event(ExportModelOperationsMixin("event"), models.Model):  # type: ignore[misc]
    class Type(models.TextChoices):
        MIXED = "MXD", _("Mixed")
        OPENS = "OPN", _("Opens")
        WOMENS = "WMN", _("Womens")

    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    team_registration_start_date = models.DateField()
    team_registration_end_date = models.DateField()
    player_registration_start_date = models.DateField()
    player_registration_end_date = models.DateField()
    ultimate_central_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    ultimate_central_slug = models.SlugField(max_length=200, default="unknown")
    location = models.CharField(max_length=255, default="unknown")
    type = models.CharField(max_length=3, choices=Type.choices, default=Type.MIXED)
    slug = models.SlugField(null=True, blank=True, db_index=True)
    max_num_teams = models.PositiveSmallIntegerField(blank=True, null=True)
    series = models.ForeignKey(Series, on_delete=models.SET_NULL, blank=True, null=True)
    team_fee = models.PositiveIntegerField(default=0)
    player_fee = models.PositiveIntegerField(default=0)
    partial_team_fee = models.PositiveIntegerField(default=0)
    is_membership_needed = models.BooleanField(default=False)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            slug = self.get_slug()
            self.slug = slug
            self.ultimate_central_slug = slug
        return super().save(*args, **kwargs)

    def get_slug(self) -> str:
        slug = slugify_max(self.title, 45)
        unique_slug = slug

        number = 1
        while Event.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{unique_slug}-{number}"
            number += 1

        return unique_slug


class Tournament(ExportModelOperationsMixin("tournament"), models.Model):  # type: ignore[misc]
    class Status(models.TextChoices):
        DRAFT = "DFT", _("Draft")
        REGISTERING = "REG", _("Registering")
        SCHEDULING = "SCH", _("Scheduling")
        LIVE = "LIV", _("Live")
        COMPLETED = "COM", _("Completed")

    event = models.OneToOneField(Event, on_delete=models.CASCADE, unique=True)
    teams = models.ManyToManyField(Team, related_name="tournaments", blank=True)
    partial_teams = models.ManyToManyField(Team, related_name="partial_reg_tournaments", blank=True)
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.DRAFT)
    logo_light = models.FileField(upload_to="tournament_logos/", blank=True, max_length=256)
    logo_dark = models.FileField(upload_to="tournament_logos/", blank=True, max_length=256)
    rules = models.TextField(blank=True, null=True)

    initial_seeding = models.JSONField(default=dict, blank=True)
    current_seeding = models.JSONField(default=dict, blank=True)
    spirit_ranking = models.JSONField(default=list, blank=True)

    use_uc_registrations = models.BooleanField(default=False)

    volunteers = models.ManyToManyField(User, related_name="tournament_volunteer", blank=True)


@receiver(m2m_changed, sender=Tournament.teams.through)
def update_seeding_on_teams_change(
    sender: Any, instance: Tournament, action: str, **kwargs: Any
) -> None:
    if action in ("post_add", "post_remove"):
        seeding = {}

        for i, team in enumerate(instance.teams.all(), start=1):
            seeding[i] = team.id

        instance.initial_seeding = seeding
        instance.current_seeding = seeding
        instance.save()


class EventRosterInvitation(ExportModelOperationsMixin("event_roster_invitation"), models.Model):  # type: ignore[misc]
    class Status(models.TextChoices):
        PENDING = "Pending", _("Pending")
        ACCEPTED = "Accepted", _("Accepted")
        DECLINED = "Declined", _("Declined")
        EXPIRED = "Expired", _("Expired")

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="event_invitations_sent"
    )
    to_player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="event_invitations_received"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    expires_on = models.DateField(default=default_invitation_expiry_date)


class Registration(ExportModelOperationsMixin("registration"), models.Model):  # type: ignore[misc]
    class Role(models.TextChoices):
        DEFAULT = "DFLT", _("Default")
        CAPTAIN = "CAP", _("Captain")
        SPIRIT_CAPTAIN = "SCAP", _("Spirit Captain")
        COACH = "COACH", _("Coach")
        ASSISTANT_COACH = "ACOACH", _("Assistant Coach")
        MANAGER = "MNGR", _("Manager")

    series_registration = models.ForeignKey(
        SeriesRegistration, on_delete=models.CASCADE, blank=True, null=True
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    is_playing = models.BooleanField(default=True)
    role = models.CharField(max_length=6, choices=Role.choices, default=Role.DEFAULT)

    class Meta:
        unique_together = ("event", "player")


class UCRegistration(ExportModelOperationsMixin("uc_registration"), models.Model):  # type: ignore[misc]
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    person = models.ForeignKey(UCPerson, on_delete=models.CASCADE)
    roles = models.JSONField()


class Pool(ExportModelOperationsMixin("pool"), models.Model):  # type: ignore[misc]
    sequence_number = models.PositiveIntegerField()
    name = models.CharField(max_length=2, default="NA")
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    initial_seeding = models.JSONField()
    results = models.JSONField()

    class Meta:
        unique_together = ["name", "tournament"]


class CrossPool(ExportModelOperationsMixin("cross_pool"), models.Model):  # type: ignore[misc]
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    initial_seeding = models.JSONField(default=dict)
    current_seeding = models.JSONField(default=dict)


class Bracket(ExportModelOperationsMixin("bracket"), models.Model):  # type: ignore[misc]
    sequence_number = models.PositiveIntegerField()
    name = models.CharField(max_length=5, default="1-8")
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    initial_seeding = models.JSONField()
    current_seeding = models.JSONField()

    class Meta:
        unique_together = ["name", "tournament"]


class PositionPool(ExportModelOperationsMixin("position_pool"), models.Model):  # type: ignore[misc]
    sequence_number = models.PositiveIntegerField()
    name = models.CharField(max_length=2, default="NA")
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

    initial_seeding = models.JSONField()
    results = models.JSONField()

    class Meta:
        unique_together = ["name", "tournament"]


class MatchScore(ExportModelOperationsMixin("match_score"), models.Model):  # type: ignore[misc]
    score_team_1 = models.PositiveIntegerField(default=0)
    score_team_2 = models.PositiveIntegerField(default=0)

    entered_by = models.ForeignKey(Player, on_delete=models.CASCADE)


class SpiritScore(ExportModelOperationsMixin("spirit_score"), models.Model):  # type: ignore[misc]
    rules = models.PositiveIntegerField()
    fouls = models.PositiveIntegerField()
    fair = models.PositiveIntegerField()
    positive = models.PositiveIntegerField()
    communication = models.PositiveIntegerField()
    total = models.PositiveIntegerField(default=0)

    mvp = models.ForeignKey(
        UCPerson, on_delete=models.CASCADE, related_name="mvp", blank=True, null=True
    )
    msp = models.ForeignKey(
        UCPerson, on_delete=models.CASCADE, related_name="msp", blank=True, null=True
    )

    mvp_v2 = models.ForeignKey(
        Player, on_delete=models.SET_NULL, related_name="mvp_v2", blank=True, null=True
    )
    msp_v2 = models.ForeignKey(
        Player, on_delete=models.SET_NULL, related_name="msp_v2", blank=True, null=True
    )

    comments = models.CharField(max_length=500, blank=True, null=True)


class TournamentField(ExportModelOperationsMixin("tournament_field"), models.Model):  # type: ignore[misc]
    name = models.CharField(max_length=25)
    address = models.CharField(max_length=25, blank=True, null=True)
    is_broadcasted = models.BooleanField(default=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    location_url = models.URLField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ["tournament", "name"]


class Match(ExportModelOperationsMixin("match"), models.Model):  # type: ignore[misc]
    class Status(models.TextChoices):
        YET_TO_FIX = "YTF", _("Yet To Fix")
        SCHEDULED = "SCH", _("Scheduled")
        COMPLETED = "COM", _("Completed")

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, blank=True, null=True)
    cross_pool = models.ForeignKey(CrossPool, on_delete=models.CASCADE, blank=True, null=True)
    bracket = models.ForeignKey(Bracket, on_delete=models.CASCADE, blank=True, null=True)
    position_pool = models.ForeignKey(PositionPool, on_delete=models.CASCADE, blank=True, null=True)
    sequence_number = (
        models.PositiveIntegerField()
    )  # For Cross Pool and Brackets to have round number

    name = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.YET_TO_FIX)
    time = models.DateTimeField(null=True, blank=True)
    field = models.ForeignKey(TournamentField, on_delete=models.SET_NULL, null=True, blank=True)
    video_url = models.URLField(max_length=255, null=True, blank=True)
    duration_mins = models.PositiveIntegerField(default=75)

    team_1 = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="team_1", blank=True, null=True
    )
    team_2 = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="team_2", blank=True, null=True
    )
    placeholder_seed_1 = models.PositiveIntegerField()
    placeholder_seed_2 = models.PositiveIntegerField()

    score_team_1 = models.PositiveIntegerField(default=0)
    score_team_2 = models.PositiveIntegerField(default=0)
    suggested_score_team_1 = models.OneToOneField(
        MatchScore,
        on_delete=models.CASCADE,
        related_name="suggested_score_team_1",
        blank=True,
        null=True,
    )
    suggested_score_team_2 = models.OneToOneField(
        MatchScore,
        on_delete=models.CASCADE,
        related_name="suggested_score_team_2",
        blank=True,
        null=True,
    )

    spirit_score_team_1 = models.OneToOneField(
        SpiritScore,
        on_delete=models.CASCADE,
        related_name="spirit_score_team_1",
        blank=True,
        null=True,
    )
    spirit_score_team_2 = models.OneToOneField(
        SpiritScore,
        on_delete=models.CASCADE,
        related_name="spirit_score_team_2",
        blank=True,
        null=True,
    )

    self_spirit_score_team_1 = models.OneToOneField(
        SpiritScore,
        on_delete=models.CASCADE,
        related_name="self_spirit_score_team_1",
        blank=True,
        null=True,
    )
    self_spirit_score_team_2 = models.OneToOneField(
        SpiritScore,
        on_delete=models.CASCADE,
        related_name="self_spirit_score_team_2",
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ["tournament", "time", "field"]


class MatchStats(models.Model):
    class Status(models.TextChoices):
        FIRST_HALF = "FH", _("First Half")
        SECOND_HALF = "SH", _("Second Half")
        COMPLETED = "COM", _("Completed")

    # For the UI to know what options to show: weather Line selection page or Offense page or Defense Page
    class TeamStatus(models.TextChoices):
        PENDING_LINE_SELECTION = "PLS", _("Pending Line Selection")
        COMPLETED_LINE_SELECTION = "CLS", _("Completed Line Selection")

    class GenderRatio(models.TextChoices):
        FEMALE = "FEMALE", _("Female")
        MALE = "MALE", _("Male")
        NA = "NA", _("NA")

    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name="stats")
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="match_stats")
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.FIRST_HALF)
    score_team_1 = models.PositiveIntegerField(default=0)
    score_team_2 = models.PositiveIntegerField(default=0)
    initial_possession = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="initial_possession"
    )
    current_possession = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="current_possession"
    )
    status_team_1 = models.CharField(
        max_length=3, choices=TeamStatus.choices, default=TeamStatus.PENDING_LINE_SELECTION
    )
    status_team_2 = models.CharField(
        max_length=3, choices=TeamStatus.choices, default=TeamStatus.PENDING_LINE_SELECTION
    )
    initial_ratio = models.CharField(
        max_length=10, choices=GenderRatio.choices, default=GenderRatio.NA
    )
    current_ratio = models.CharField(
        max_length=10, choices=GenderRatio.choices, default=GenderRatio.NA
    )


class MatchEvent(models.Model):
    class EventType(models.TextChoices):
        LINE_SELECTED = "LS", _("Line Selected")
        SCORE = "SC", _("Score")
        DROP = "DR", _("Drop")
        THROWAWAY = "TA", _("Throwaway")
        BLOCK = "BL", _("Block")

    class Mode(models.TextChoices):
        OFFENSE = "OF", _("Offense")
        DEFENSE = "DE", _("Defense")

    stats = models.ForeignKey(MatchStats, on_delete=models.CASCADE, related_name="events")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="match_events")
    players = models.ManyToManyField(Player, related_name="match_events_played")
    started_on = models.CharField(max_length=3, choices=Mode.choices)
    time = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=3, choices=EventType.choices)

    scored_by = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="match_events_scored", blank=True, null=True
    )
    assisted_by = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="match_events_assisted",
        blank=True,
        null=True,
    )
    drop_by = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="match_events_drops", blank=True, null=True
    )
    throwaway_by = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="match_events_throwaways",
        blank=True,
        null=True,
    )
    block_by = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name="match_events_blocks", blank=True, null=True
    )
