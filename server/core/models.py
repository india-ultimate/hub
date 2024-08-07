from pathlib import Path
from typing import Any

from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.constants import ANNUAL_MEMBERSHIP_AMOUNT, MAJOR_AGE, SPONSORED_ANNUAL_MEMBERSHIP_AMOUNT
from server.utils import slugify_max


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
            slug = self.get_slug()
            self.slug = slug
            self.ultimate_central_slug = slug
        return super().save(*args, **kwargs)

    def get_slug(self) -> str:
        slug = slugify_max(self.name, 45)
        unique_slug = slug

        number = 1
        while Team.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{unique_slug}-{number}"
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


@receiver(pre_save, sender=Accreditation)
def update_accreditation_validity(
    sender: Any, instance: Accreditation, raw: bool, **kwargs: Any
) -> None:
    if raw:
        return

    instance.full_clean()  # Ensure instance.date is a datetime.date object
    instance.is_valid = instance.date > (now() - relativedelta(months=18)).date()
    return
