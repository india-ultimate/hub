import uuid
from pathlib import Path
from typing import Any

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import m2m_changed, pre_save
from django.dispatch import receiver
from django.template.defaultfilters import slugify
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.constants import ANNUAL_MEMBERSHIP_AMOUNT, MAJOR_AGE, SPONSORED_ANNUAL_MEMBERSHIP_AMOUNT


class User(AbstractUser):
    phone = models.CharField(max_length=20)
    email = models.EmailField()

    is_tournament_admin = models.BooleanField(default=False)


class StatesUTs(models.TextChoices):
    AN = "AN", _("Andaman and Nicobar Islands")
    AP = "AP", _("Andhra Pradesh")
    AR = "AR", _("Arunachal Pradesh")
    AS = "AS", _("Assam")
    BR = "BR", _("Bihar")
    CDG = "CDG", _("Chandigarh")
    CG = "CG", _("Chhattisgarh")
    DNH = "DNH", _("Dadra and Nagar Haveli")
    DD = "DD", _("Daman and Diu")
    DL = "DL", _("Delhi")
    GA = "GA", _("Goa")
    GJ = "GJ", _("Gujarat")
    HR = "HR", _("Haryana")
    HP = "HP", _("Himachal Pradesh")
    JK = "JK", _("Jammu and Kashmir")
    JH = "JH", _("Jharkhand")
    KA = "KA", _("Karnataka")
    KL = "KL", _("Kerala")
    LK = "LK", _("Ladakh")
    LD = "LD", _("Lakshadweep")
    MP = "MP", _("Madhya Pradesh")
    MH = "MH", _("Maharashtra")
    MN = "MN", _("Manipur")
    ML = "ML", _("Meghalaya")
    MZ = "MZ", _("Mizoram")
    NL = "NL", _("Nagaland")
    OR = "OR", _("Odisha")
    PY = "PY", _("Puducherry")
    PB = "PB", _("Punjab")
    RJ = "RJ", _("Rajasthan")
    SK = "SK", _("Sikkim")
    TN = "TN", _("Tamil Nadu")
    TL = "TL", _("Telangana")
    TR = "TR", _("Tripura")
    UP = "UP", _("Uttar Pradesh")
    UK = "UK", _("Uttarakhand")
    WB = "WB", _("West Bengal")


def upload_team_logos(instance: "Team", filename: str) -> str:
    parent = Path("team_logos")
    path = Path(filename)
    new_name = f"{path.stem}-{get_random_string(12)}{path.suffix}"
    return str(parent / new_name)


class Team(ExportModelOperationsMixin("team"), models.Model):  # type: ignore[misc]
    ultimate_central_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    ultimate_central_creator_id = models.PositiveIntegerField(null=True, blank=True)
    facebook_url = models.URLField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    name = models.CharField(max_length=100)
    ultimate_central_slug = models.SlugField(default="unknown")
    admins = models.ManyToManyField(User, related_name="admin_teams")
    state_ut = models.CharField(max_length=5, choices=StatesUTs.choices, null=True, blank=True)
    city = models.CharField(max_length=30, null=True, blank=True)
    image = models.FileField(upload_to=upload_team_logos, blank=True, max_length=256)
    slug = models.SlugField(null=True, blank=True, db_index=True)

    class CategoryTypes(models.TextChoices):
        CLUB = "Club", _("Club")
        COLLEGE = "College", _("College")
        STATE = "State", _("State")
        NATIONAL = "National", _("National")

    category = models.CharField(max_length=25, choices=CategoryTypes.choices, null=True, blank=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = self.get_slug()
        return super().save(*args, **kwargs)

    def get_slug(self) -> str:
        slug = slugify(self.name)
        unique_slug = slug

        number = 1
        while Team.objects.filter(slug=unique_slug).exists():
            unique_slug = slugify(f"{slug}-{number}")
            number += 1

        return unique_slug


class Player(ExportModelOperationsMixin("player"), models.Model):  # type: ignore[misc]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="player_profile")
    date_of_birth = models.DateField()

    class GenderTypes(models.TextChoices):
        MALE = "M", _("Male")
        FEMALE = "F", _("Female")
        OTHER = "O", _("Other")

    gender = models.CharField(max_length=5, choices=GenderTypes.choices)
    other_gender = models.CharField(max_length=30, null=True, blank=True)

    class MatchupTypes(models.TextChoices):
        MALE = "M", _("Male matching")
        FEMALE = "F", _("Female matching")

    match_up = models.CharField(max_length=30, choices=MatchupTypes.choices)
    city = models.CharField(max_length=100)
    state_ut = models.CharField(max_length=5, choices=StatesUTs.choices, null=True, blank=True)
    not_in_india = models.BooleanField(default=False)
    teams = models.ManyToManyField(Team, related_name="players")

    class OccupationTypes(models.TextChoices):
        STUDENT = "Student", _("Student")
        COLLEGE_STUDENT = "College-Student", _("College Student")
        BUSINESS = "Business", _("Own business")
        GOVERNMENT = "Government", _("Government")
        NONPROFIT = "Non-profit", _("NGO / NPO")
        OTHER = "Other", _("Other")
        UNEMPLOYED = "Unemployed", _("Unemployed")

    occupation = models.CharField(
        max_length=25, choices=OccupationTypes.choices, null=True, blank=True
    )
    educational_institution = models.CharField(max_length=100, null=True, blank=True)
    ultimate_central_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    sponsored = models.BooleanField(default=False)
    imported_data = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.user.get_full_name()

    @property
    def membership_amount(self) -> int:
        return SPONSORED_ANNUAL_MEMBERSHIP_AMOUNT if self.sponsored else ANNUAL_MEMBERSHIP_AMOUNT

    @property
    def is_minor(self) -> bool:
        today = now().date()
        dob = self.date_of_birth
        age = (today.year - dob.year) + (today.month - dob.month) / 12 + (today.day - dob.day) / 365
        return age < MAJOR_AGE


class UCPerson(ExportModelOperationsMixin("uc_person"), models.Model):  # type: ignore[misc]
    email = models.EmailField(db_index=True)
    dominant_hand = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(db_index=True)
    image_url = models.URLField(null=True, blank=True)


class Guardianship(ExportModelOperationsMixin("guardianship"), models.Model):  # type: ignore[misc]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    player = models.OneToOneField(Player, on_delete=models.CASCADE, unique=True)

    class Relation(models.TextChoices):
        MO = "MO", _("Mother")
        FA = "FA", _("Father")
        LG = "LG", _("Legal Guardian")

    relation = models.TextField(max_length=2, choices=Relation.choices)


class Event(ExportModelOperationsMixin("event"), models.Model):  # type: ignore[misc]
    class Type(models.TextChoices):
        MIXED = "MXD", _("Mixed")
        OPENS = "OPN", _("Opens")
        WOMENS = "WMN", _("Womens")

    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_start_date = models.DateField(null=True, blank=True)
    registration_end_date = models.DateField(null=True, blank=True)
    ultimate_central_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    ultimate_central_slug = models.SlugField(max_length=200, default="unknown")
    location = models.CharField(max_length=255, default="unknown")
    type = models.CharField(max_length=3, choices=Type.choices, default=Type.MIXED)
    slug = models.SlugField(null=True, blank=True, db_index=True)


class Tournament(ExportModelOperationsMixin("tournament"), models.Model):  # type: ignore[misc]
    class Status(models.TextChoices):
        DRAFT = "DFT", _("Draft")
        REGISTERING = "REG", _("Registering")
        SCHEDULING = "SCH", _("Scheduling")
        LIVE = "LIV", _("Live")
        COMPLETED = "COM", _("Completed")

    event = models.OneToOneField(Event, on_delete=models.CASCADE, unique=True)
    teams = models.ManyToManyField(Team, related_name="tournaments")
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.DRAFT)
    logo_light = models.FileField(upload_to="tournament_logos/", blank=True, max_length=256)
    logo_dark = models.FileField(upload_to="tournament_logos/", blank=True, max_length=256)
    rules = models.TextField(blank=True, null=True)

    initial_seeding = models.JSONField(default=dict)
    current_seeding = models.JSONField(default=dict)
    spirit_ranking = models.JSONField(default=list)


@receiver(m2m_changed, sender=Tournament.teams.through)
def update_seeding_on_teams_change(
    sender: Any, instance: Tournament, action: str, **kwargs: Any
) -> None:
    if action == "post_add":
        seeding = {}

        for i, team in enumerate(instance.teams.all(), start=1):
            seeding[i] = team.id

        instance.initial_seeding = seeding
        instance.current_seeding = seeding
        instance.save()


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

    comments = models.CharField(max_length=500, blank=True, null=True)


class TournamentField(ExportModelOperationsMixin("tournament_field"), models.Model):  # type: ignore[misc]
    name = models.CharField(max_length=25)
    address = models.CharField(max_length=25, blank=True, null=True)
    is_broadcasted = models.BooleanField(default=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)

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


class Registration(ExportModelOperationsMixin("registration"), models.Model):  # type: ignore[misc]
    class Role(models.TextChoices):
        DEFAULT = "DFLT", _("Default")
        CAPTAIN = "CAP", _("Captain")
        SPIRIT_CAPTAIN = "SCAP", _("Spirit Captain")
        COACH = "COACH", _("Coach")
        ASSISTANT_COACH = "ACOACH", _("Assistant Coach")
        MANAGER = "MNGR", _("Manager")

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    is_playing = models.BooleanField(default=True)
    role = models.CharField(max_length=6, choices=Role.choices, default=Role.DEFAULT)


class UCRegistration(ExportModelOperationsMixin("uc_registration"), models.Model):  # type: ignore[misc]
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    person = models.ForeignKey(UCPerson, on_delete=models.CASCADE)
    roles = models.JSONField()


class Membership(ExportModelOperationsMixin("membership"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    membership_number = models.CharField(max_length=20, unique=True)
    is_annual = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True)
    is_active = models.BooleanField(default=False)
    waiver_valid = models.BooleanField(default=False)
    waiver_signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    waiver_signed_at = models.DateTimeField(blank=True, null=True)


def create_transaction_from_order_data(cls: Any, data: dict[str, Any]) -> Any:
    fields = {f.name for f in cls._meta.fields}
    attrs_data = {key: value for key, value in data.items() if key in fields}
    transaction = cls.objects.create(**attrs_data)
    players = data.get("players", [])
    for player in players:
        transaction.players.add(player)
    return transaction


class RazorpayTransaction(ExportModelOperationsMixin("razorpay_transaction"), models.Model):  # type: ignore[misc]
    class TransactionStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    order_id = models.CharField(primary_key=True, max_length=255)
    payment_id = models.CharField(max_length=255)
    payment_signature = models.CharField(max_length=255)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    # FIXME: payment_date is actually order_date, currently
    payment_date = models.DateTimeField(auto_now_add=True)
    # NOTE: These dates are for the membership for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the membership on payment success.
    start_date = models.DateField(default="1900-01-01")
    end_date = models.DateField(default="1900-01-01")
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self) -> str:
        return self.order_id

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "RazorpayTransaction":
        return create_transaction_from_order_data(cls, data)


class PhonePeTransaction(ExportModelOperationsMixin("phonepe_transaction"), models.Model):  # type: ignore[misc]
    class TransactionStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        ERROR = "error", _("Error")
        DECLINED = "declined", _("Declined")

    transaction_id = models.UUIDField(primary_key=True)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    transaction_date = models.DateTimeField(auto_now_add=True)
    # NOTE: These dates are for the membership for which the transaction is
    # being done. We store these dates when the order is created, and use them
    # to update the membership on payment success.
    start_date = models.DateField(default="1900-01-01")
    end_date = models.DateField(default="1900-01-01")
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self) -> str:
        return str(self.transaction_id)

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "PhonePeTransaction":
        return create_transaction_from_order_data(cls, data)


class ManualTransaction(ExportModelOperationsMixin("manual_transaction"), models.Model):  # type: ignore[misc]
    transaction_id = models.CharField(primary_key=True, max_length=255)
    amount = models.IntegerField()
    currency = models.CharField(max_length=5)
    payment_date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    players = models.ManyToManyField(Player)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True)
    validated = models.BooleanField(default=False)
    validation_comment = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return self.transaction_id

    @classmethod
    def create_from_order_data(cls, data: dict[str, Any]) -> "ManualTransaction":
        return create_transaction_from_order_data(cls, data)


def upload_vaccination_certificates(instance: "Vaccination", filename: str) -> str:
    parent = Path("vaccination_certificates")
    path = Path(filename)
    new_name = f"{path.stem}-{get_random_string(12)}{path.suffix}"
    return str(parent / new_name)


class Vaccination(ExportModelOperationsMixin("vaccination"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    is_vaccinated = models.BooleanField()

    class VaccinationName(models.TextChoices):
        COVISHIELD = "CVSHLD", _("Covishield")
        COVAXIN = "CVXN", _("Covaxin")
        MODERNA = "MDRN", _("Moderna")
        SPUTNIK = "SPTNK", _("Sputnik")
        JOHNSON_AND_JOHNSON = "JNJ", _("Johnson & Johnson")

    name = models.CharField(
        max_length=10,
        choices=VaccinationName.choices,
        blank=True,
        null=True,
    )
    certificate = models.FileField(
        upload_to=upload_vaccination_certificates, blank=True, max_length=256
    )
    explain_not_vaccinated = models.TextField(blank=True, null=True)


class Accreditation(ExportModelOperationsMixin("accreditation"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    is_valid = models.BooleanField()

    class AccreditationLevel(models.TextChoices):
        STANDARD = "STD", _("Standard")
        ADVANCED = "ADV", _("Advanced")

    level = models.CharField(max_length=10, choices=AccreditationLevel.choices)
    date = models.DateField()
    certificate = models.FileField(upload_to="accreditation_certificates/", max_length=256)
    wfdf_id = models.PositiveIntegerField(unique=True, null=True, blank=True)


class CollegeId(ExportModelOperationsMixin("college_id"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="college_id")
    expiry = models.DateField()
    card_front = models.FileField(upload_to="college_ids/", max_length=256)
    card_back = models.FileField(upload_to="college_ids/", max_length=256)
    ocr_name = models.PositiveIntegerField(null=True, blank=True)
    ocr_college = models.PositiveIntegerField(null=True, blank=True)


class CommentaryInfo(ExportModelOperationsMixin("commentary_info"), models.Model):  # type: ignore[misc]
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="commentary_info")

    jersey_number = models.PositiveIntegerField()
    ultimate_origin = models.TextField()
    ultimate_attraction = models.TextField()
    ultimate_fav_role = models.TextField()
    ultimate_fav_exp = models.TextField()
    interests = models.TextField()
    fun_fact = models.TextField()


@receiver(pre_save, sender=Membership)
def create_membership_number(sender: Any, instance: Membership, raw: bool, **kwargs: Any) -> None:
    if raw or instance.membership_number:
        return

    instance.membership_number = str(uuid.uuid4())[:8]
    return


@receiver(pre_save, sender=Accreditation)
def update_accreditation_validity(
    sender: Any, instance: Accreditation, raw: bool, **kwargs: Any
) -> None:
    if raw:
        return

    instance.full_clean()  # Ensure instance.date is a datetime.date object
    instance.is_valid = instance.date > (now() - relativedelta(months=18)).date()
    return
