import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver


class User(AbstractUser):
    is_player = models.BooleanField(default=False)
    is_guardian = models.BooleanField(default=False)
    phone = models.CharField(max_length=20)
    email = models.EmailField()


class Player(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="player_profile")
    guardian = models.ForeignKey("Guardian", on_delete=models.SET_NULL, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    state_ut = models.CharField(max_length=100)
    team_name = models.CharField(max_length=100)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    educational_institution = models.CharField(max_length=100, null=True, blank=True)
    india_ultimate_profile = models.URLField(null=True, blank=True)


class Guardian(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="guardian_profile")
    full_name = models.CharField(max_length=200)
    relation = models.TextField(max_length=200)


class Event(models.Model):
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()


class Membership(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    membership_number = models.CharField(max_length=20, unique=True)
    is_annual = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE, blank=True, null=True)
    is_active = models.BooleanField(default=True)


class Vaccination(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE)
    is_vaccinated = models.BooleanField()
    vaccination_name = models.CharField(max_length=100, blank=True)
    vaccination_certificate = models.FileField(upload_to="vaccination_certificates/", blank=True)
    explain_not_vaccinated = models.TextField(blank=True)


@receiver(pre_save, sender=Membership)
def create_membership_number(sender, instance, raw, **kwargs):
    if raw or instance.membership_number:
        return

    # FIXME: What are good ways to membership numbers?
    instance.membership_number = str(uuid.uuid4())[:8]
    return
