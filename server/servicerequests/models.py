from typing import Any

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from server.core.models import Player, User


class ServiceRequestType(models.TextChoices):
    REQUEST_SPONSORED_MEMBERSHIP = "REQUEST_SPONSORED_MEMBERSHIP", "Request Sponsored Membership"


class ServiceRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class ServiceRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=ServiceRequestType.choices)
    message = models.TextField()
    status = models.CharField(
        max_length=50, choices=ServiceRequestStatus.choices, default=ServiceRequestStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    service_players = models.ManyToManyField(Player, blank=True, related_name="service_requests")


@receiver(post_save, sender=ServiceRequest)
def handle_sponsored_membership_approval(
    sender: Any, instance: ServiceRequest, created: bool, **kwargs: Any
) -> None:
    """
    When a service request for sponsored membership is approved,
    update the user's player profile to set sponsored=True.
    """
    # Only process if this is an update (not creation), status is APPROVED, and type is sponsored membership
    if (
        not created
        and instance.status == ServiceRequestStatus.APPROVED
        and instance.type == ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP
    ):
        # Update all service players' sponsored field
        for player in instance.service_players.all():
            player.sponsored = True
            player.save(update_fields=["sponsored"])
