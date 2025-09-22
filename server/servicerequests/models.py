from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string

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
def handle_service_request_status_change(
    sender: Any, instance: ServiceRequest, created: bool, **kwargs: Any
) -> None:
    """
    When a service request status changes to approved or rejected,
    send email notification to the user and handle sponsored membership approval.
    """
    # Only process if this is an update (not creation) and status is APPROVED or REJECTED
    if not created and instance.status in [
        ServiceRequestStatus.APPROVED,
        ServiceRequestStatus.REJECTED,
    ]:
        # Send email notification
        send_service_request_notification_email(instance)

        # Handle sponsored membership approval logic
        if (
            instance.status == ServiceRequestStatus.APPROVED
            and instance.type == ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP
        ):
            # Update all service players' sponsored field
            for player in instance.service_players.all():
                player.sponsored = True
                player.save(update_fields=["sponsored"])


def send_service_request_notification_email(service_request: ServiceRequest) -> None:
    """
    Send email notification to the user when their service request is approved or rejected.
    """
    try:
        # Use single unified template for both approved and rejected requests
        template_name = "emails/service_request_notification.html"

        # Determine subject based on status
        if service_request.status == ServiceRequestStatus.APPROVED:
            subject = f"Service Request Approved - {service_request.get_type_display()}"
        else:  # REJECTED
            subject = f"Service Request Update - {service_request.get_type_display()}"

        # Prepare email context
        context = {
            "service_request": service_request,
            "site_url": settings.EMAIL_INVITATION_BASE_URL,
        }

        # Render HTML message
        html_message = render_to_string(template_name, context)

        # Create plain text version
        plain_message = f"""
Service Request Update

Request Type: {service_request.get_type_display()}
Status: {service_request.get_status_display()}
Submitted: {service_request.created_at.strftime('%B %d, %Y at %I:%M %p')}
Updated: {service_request.updated_at.strftime('%B %d, %Y at %I:%M %p')}

"""

        if service_request.message:
            plain_message += f"Your Message: {service_request.message}\n\n"

        if service_request.service_players.exists():
            plain_message += "Players Affected:\n"
            for player in service_request.service_players.all():
                plain_message += f"- {player.user.get_full_name()} ({player.user.email})\n"
            plain_message += "\n"

        if service_request.status == ServiceRequestStatus.APPROVED:
            plain_message += "🎉 Great news! Your service request has been approved.\n\n"
        else:
            plain_message += "📋 We have reviewed your service request and unfortunately, it has not been approved at this time.\n\n"
            plain_message += "If you have any questions about this decision or would like to submit a new request, please don't hesitate to contact our support team.\n\n"

        plain_message += "Thank you for using the India Ultimate Hub services.\n\n"
        plain_message += "This is an automated message from the India Ultimate Hub.\n"
        plain_message += "Please do not reply directly to this email."

        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[service_request.user.email],
            fail_silently=True,
            html_message=html_message,
        )

    except Exception as e:
        # Log the error but don't fail the service request update
        print(f"Error sending service request notification email: {e}")
