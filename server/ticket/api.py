from typing import Any

import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from ninja import File, Router
from ninja.files import UploadedFile

from server.core.models import User
from server.ticket.models import Ticket, TicketMessage
from server.ticket.schema import (
    TicketCreateSchema,
    TicketDetailSchema,
    TicketListItemSchema,
    TicketMessageCreateSchema,
    TicketUpdateSchema,
)
from server.types import message_response

# Initialize Cloudinary
cloudinary.config(
    cloud_name=django_settings.CLOUDINARY_CLOUD_NAME,
    api_key=django_settings.CLOUDINARY_API_KEY,
    api_secret=django_settings.CLOUDINARY_API_SECRET,
)


class AuthenticatedHttpRequest(HttpRequest):
    user: User


ticket_api = Router()


def get_staff_emails() -> list[str]:
    """Get a list of all staff email addresses"""
    return list(User.objects.filter(is_staff=True).values_list("email", flat=True))


@ticket_api.get("/", response=list[TicketListItemSchema])
def list_tickets(
    request: AuthenticatedHttpRequest, status: str | None = None, created_by_me: bool = False
) -> QuerySet[Ticket]:
    """Get list of all tickets"""
    query = Ticket.objects.all()

    if status:
        query = query.filter(status=status)

    # Filter by tickets created by the current user
    if created_by_me:
        query = query.filter(created_by=request.user)

    return query.annotate(message_count=Count("messages")).order_by("-created_at")


@ticket_api.get("/{ticket_id}", response=TicketDetailSchema)
def get_ticket(request: AuthenticatedHttpRequest, ticket_id: int) -> Ticket:
    """Get ticket details and messages"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return ticket


@ticket_api.post("/", response={201: TicketDetailSchema})
def create_ticket(
    request: AuthenticatedHttpRequest, data: TicketCreateSchema
) -> tuple[int, Ticket]:
    """Create a new ticket"""
    ticket = Ticket.objects.create(
        title=data.title,
        description=data.description,
        priority=data.priority,
        category=data.category,
        created_by=request.user,
    )

    # Get all staff emails to notify
    staff_emails = get_staff_emails()

    # Send notification email to all staff if we have staff emails
    if staff_emails:
        try:
            # Plain text version
            plain_message = "A new support ticket has been created:\n\n"
            plain_message += f"Ticket #{ticket.id}: {ticket.title}\n"
            plain_message += f"Priority: {ticket.get_priority_display()}\n"
            plain_message += (
                f"Created by: {ticket.created_by.first_name} {ticket.created_by.last_name}\n"
            )
            plain_message += f"Description: {ticket.description}\n\n"
            plain_message += "Please respond to this ticket at your earliest convenience."

            # HTML version with template
            context = {
                "ticket": ticket,
                "site_url": settings.EMAIL_INVITATION_BASE_URL,
            }
            html_message = render_to_string("emails/new_ticket.html", context)

            subject = f"New Support Ticket: #{ticket.id} - {ticket.title}"

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=staff_emails,
                fail_silently=True,
                html_message=html_message,
            )
        except Exception as e:
            # Log the error but don't fail the ticket creation
            print(f"Error sending email notification: {e}")

    return 201, ticket


@ticket_api.put("/{ticket_id}", response={200: TicketDetailSchema, 403: message_response})
def update_ticket(
    request: AuthenticatedHttpRequest, ticket_id: int, data: TicketUpdateSchema
) -> tuple[int, Ticket | dict[str, Any]]:
    """Update ticket details"""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Staff can update any ticket, but regular users can only update status on their own tickets
    if not request.user.is_staff and ticket.created_by != request.user:
        # Regular users can only update tickets they created
        return 403, {"message": "You don't have permission to update this ticket"}

    # Restrict what non-staff users can update
    if not request.user.is_staff:
        # Regular users can only update tickets they created
        if data.status:
            ticket.status = data.status
    else:
        # Staff can update all fields
        if data.title:
            ticket.title = data.title
        if data.description:
            ticket.description = data.description
        if data.status:
            ticket.status = data.status
        if data.priority:
            ticket.priority = data.priority
        if data.category:
            ticket.category = data.category
        if data.assigned_to_id:
            ticket.assigned_to = get_object_or_404(User, id=data.assigned_to_id)

    ticket.save()
    return 200, ticket


@ticket_api.post("/{ticket_id}/message", response={201: TicketDetailSchema, 400: message_response})
def add_message(
    request: AuthenticatedHttpRequest,
    ticket_id: int,
    message_details: TicketMessageCreateSchema,
    attachment: UploadedFile | None = File(None),  # noqa: B008
) -> tuple[int, Ticket | dict[str, str]]:
    """Add message to ticket (with optional attachment: image or PDF, max 20MB, uploaded to Cloudinary)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    message = message_details.message

    # Validate and upload attachment if present
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "application/pdf",
    ]
    max_size = 20 * 1024 * 1024  # 20MB
    attachment_url = None
    if attachment:
        if attachment.content_type not in allowed_types:
            return 400, {"message": "Only image files and PDF are allowed as attachments."}
        if attachment.size is not None and attachment.size > max_size:
            return 400, {"message": "Attachment size must not exceed 20MB."}
        # Upload to Cloudinary
        try:
            result = cloudinary.uploader.upload(
                attachment.file,
                resource_type="auto",
                folder="ticket_attachments/",
                use_filename=True,
                unique_filename=True,
            )
            attachment_url = result.get("secure_url")
        except Exception as e:
            return 400, {"message": f"Failed to upload attachment: {e}"}

    TicketMessage.objects.create(
        ticket=ticket,
        sender=request.user,
        message=message,
        attachment=attachment_url,
    )

    # If ticket is closed or resolved, set it back to in progress when user adds message
    if (
        ticket.status in [Ticket.Status.CLOSED, Ticket.Status.RESOLVED]
        and ticket.created_by == request.user
    ):
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save()

    # Get all parties involved in the ticket conversation
    recipients = set()

    # Add ticket creator if they have an email and are not the sender
    if ticket.created_by.email and ticket.created_by != request.user:
        recipients.add(ticket.created_by.email)

    # Add assigned staff if they have an email and are not the sender
    if ticket.assigned_to and ticket.assigned_to.email and ticket.assigned_to != request.user:
        recipients.add(ticket.assigned_to.email)

    # Add all users who have previously sent messages (except the current sender)
    previous_senders = (
        TicketMessage.objects.filter(ticket=ticket)
        .exclude(sender=request.user)
        .values_list("sender__email", flat=True)
        .distinct()
    )

    for email in previous_senders:
        if email:  # Make sure email is not None or empty
            recipients.add(email)

    # Convert set to list for send_mail
    recipient_list = list(recipients)

    # Send the email if we have recipients
    if recipient_list:
        try:
            # Plain text version
            plain_message = f"A new message has been added to ticket #{ticket.id}:\n\n"
            plain_message += f"From: {request.user.first_name} {request.user.last_name}\n"
            plain_message += f"Message: {message}\n\n"
            plain_message += "You can view and respond to this ticket on the website."

            # HTML version with template
            context = {
                "ticket": ticket,
                "sender": request.user,
                "message": message,
                "site_url": settings.EMAIL_INVITATION_BASE_URL,
            }
            html_message = render_to_string("emails/ticket_message.html", context)

            subject = f"New message on Ticket #{ticket.id}: {ticket.title}"

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=recipient_list,
                fail_silently=True,
                html_message=html_message,
            )
        except Exception as e:
            # Log the error but don't fail the message creation
            print(f"Error sending email notification: {e}")

    return 201, ticket
