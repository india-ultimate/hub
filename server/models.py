import uuid
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    phone = models.CharField(max_length=20)
    email = models.EmailField()


class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="player_profile")
    date_of_birth = models.DateField()

    class GenderTypes(models.TextChoices):
        MALE = "M", _("Male")
        FEMALE = "F", _("Female")
        OTHER = "O", _("Other")

    gender = models.CharField(max_length=5, choices=GenderTypes.choices)
    other_gender = models.CharField(max_length=30, null=True, blank=True)
    city = models.CharField(max_length=100)

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

    state_ut = models.CharField(max_length=5, choices=StatesUTs.choices, null=True, blank=True)
    not_in_india = models.BooleanField(default=False)
    team_name = models.CharField(max_length=100)

    class OccupationTypes(models.TextChoices):
        STUDENT = "Student", _("Student")
        BUSINESS = "Business", _("Own business")
        GOVERNMENT = "Government", _("Government")
        NONPROFIT = "Non-profit", _("NGO / NPO")
        OTHER = "Other", _("Other")
        UNEMPLOYED = "Unemployed", _("Unemployed")

    occupation = models.CharField(
        max_length=25, choices=OccupationTypes.choices, null=True, blank=True
    )
    educational_institution = models.CharField(max_length=100, null=True, blank=True)
    ultimate_central_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    sponsored = models.BooleanField(default=False)


class Guardianship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    player = models.OneToOneField(Player, on_delete=models.CASCADE, unique=True)

    class Relation(models.TextChoices):
        MO = "MO", _("Mother")
        FA = "FA", _("Father")
        LG = "LG", _("Legal Guardian")

    relation = models.TextField(max_length=2, choices=Relation.choices)


class Event(models.Model):
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    ultimate_central_id = models.PositiveIntegerField(unique=True, null=True, blank=True)
    ultimate_central_slug = models.SlugField(default="unknown")


class Team(models.Model):
    ultimate_central_id = models.PositiveIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    ultimate_central_creator_id = models.PositiveIntegerField(null=True, blank=True)
    facebook_url = models.URLField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    name = models.CharField(max_length=100)


class UCPerson(models.Model):
    email = models.EmailField(db_index=True)
    dominant_hand = models.CharField(max_length=10, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(db_index=True)
    image_url = models.URLField(null=True, blank=True)


class UCRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    person = models.ForeignKey(UCPerson, on_delete=models.CASCADE)
    roles = models.JSONField()


class Membership(models.Model):
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


class RazorpayTransaction(models.Model):
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
        fields = {f.name for f in RazorpayTransaction._meta.fields}
        attrs_data = {key: value for key, value in data.items() if key in fields}
        transaction = cls.objects.create(**attrs_data)
        players = data.get("players", [])
        for player in players:
            transaction.players.add(player)
        return transaction


class Vaccination(models.Model):
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
    certificate = models.FileField(upload_to="vaccination_certificates/", blank=True)
    explain_not_vaccinated = models.TextField(blank=True, null=True)


@receiver(pre_save, sender=Membership)
def create_membership_number(sender: Any, instance: Membership, raw: bool, **kwargs: Any) -> None:
    if raw or instance.membership_number:
        return

    instance.membership_number = str(uuid.uuid4())[:8]
    return
