from typing import Any, Literal

import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from ninja import File, Query, Router
from ninja.files import UploadedFile
from ninja.pagination import PageNumberPagination, paginate

from server.core.models import User
from server.ticket.models import Ticket, TicketMessage
from server.ticket.schema import (
    TicketCreateSchema,
    TicketDetailSchema,
    TicketListItemSchema,
    TicketMessageCreateSchema,
    TicketUpdateSchema,
)
from server.ticket.search import ranked, search_words
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


Status = Literal["OPN", "PRG", "RES"]
Sort = Literal["relevance", "newest", "upvotes"]
PAGE_SIZE = 20


def _count(rows: QuerySet[Any]) -> Coalesce:
    """How many of `rows`, already filtered to the outer ticket, there are.

    A subquery rather than Count over a join: two joined counts multiply each
    other, and a subquery is only evaluated for the rows a page returns.
    """
    return Coalesce(
        Subquery(rows.order_by().values("ticket").annotate(n=Count("pk")).values("n")),
        0,
        output_field=IntegerField(),
    )


def visible_tickets(user: User) -> QuerySet[Ticket]:
    """The tickets `user` may see: a private one only to its creator and staff.

    Each comes with its upvote count and whether `user` is one of them.
    """
    upvotes = Ticket.upvoters.through.objects.filter(ticket=OuterRef("pk"))
    tickets = Ticket.objects.annotate(
        upvote_count=_count(upvotes),
        has_upvoted=Exists(upvotes.filter(user=user)),
    )
    if user.is_staff:
        return tickets
    return tickets.filter(Q(is_private=False) | Q(created_by=user))


@ticket_api.get("/", response=list[TicketListItemSchema])
@paginate(PageNumberPagination, page_size=PAGE_SIZE)
def list_tickets(
    request: AuthenticatedHttpRequest,
    q: str = "",
    status: list[Status] = Query(None),  # noqa: B008  # repeatable: ?status=OPN&status=PRG
    category: Ticket.Category | None = None,
    mine: bool = False,
    upvoted: bool = False,
    exclude_private: bool = False,
    sort: Sort | None = None,
) -> QuerySet[Ticket]:
    """One page of the tickets the user may see, searched, filtered and sorted.

    Everything starts from visible_tickets(), so someone else's private ticket
    is never matched, listed or counted.
    """
    query: QuerySet[Ticket] = visible_tickets(request.user).annotate(
        message_count=_count(TicketMessage.objects.filter(ticket=OuterRef("pk")))
    )
    if status:
        query = query.filter(status__in=status)
    if category:
        query = query.filter(category=category)
    if mine:
        query = query.filter(created_by=request.user)
    if upvoted:
        query = query.filter(upvoters=request.user)
    if exclude_private:
        query = query.filter(is_private=False)

    words = search_words(q)
    if words:
        query = ranked(query, words)

    # -id last, so tickets created in the same instant keep one page order
    if sort == "upvotes":
        return query.order_by("-upvote_count", "-created_at", "-id")
    if words and sort in (None, "relevance"):
        return query.order_by("-score", "-created_at", "-id")
    return query.order_by("-created_at", "-id")


@ticket_api.get("/{ticket_id}", response=TicketDetailSchema)
def get_ticket(request: AuthenticatedHttpRequest, ticket_id: int) -> Ticket:
    """Get ticket details and messages"""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
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
        is_private=data.is_private,
        created_by=request.user,
    )

    # Get all emails from settings to notify
    notification_emails = settings.NEW_TICKET_NOTIFICATION_EMAILS

    # Send notification email to all emails if we have emails
    if notification_emails:
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
                recipient_list=notification_emails,
                fail_silently=True,
                html_message=html_message,
            )
        except Exception as e:
            # Log the error but don't fail the ticket creation
            print(f"Error sending email notification: {e}")

    # Read back for the upvote fields the response carries
    return 201, visible_tickets(request.user).get(id=ticket.id)


@ticket_api.put("/{ticket_id}", response={200: TicketDetailSchema, 403: message_response})
def update_ticket(
    request: AuthenticatedHttpRequest, ticket_id: int, data: TicketUpdateSchema
) -> tuple[int, Ticket | dict[str, Any]]:
    """Update ticket details"""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)

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

    # Both the creator and staff can hide a ticket, or show it again
    if data.is_private is not None:
        ticket.is_private = data.is_private

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
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
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

    # If ticket is resolved, set it back to in progress when creator adds message
    if ticket.status == Ticket.Status.RESOLVED and ticket.created_by == request.user:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save()

    # Get all parties involved in the ticket conversation
    recipients = set()

    # Add ticket creator if they have an email and are not the sender
    if ticket.created_by.email and ticket.created_by != request.user:
        recipients.add(ticket.created_by.email)

    # Add assigned staff if they have an email and are not the sender. Anyone can
    # be assigned, but only staff can open a private ticket.
    assignee = ticket.assigned_to
    if (
        assignee
        and assignee.email
        and assignee != request.user
        and (assignee.is_staff or not ticket.is_private)
    ):
        recipients.add(assignee.email)

    # Add all users who have previously sent messages (except the current sender)
    previous_messages = TicketMessage.objects.filter(ticket=ticket).exclude(sender=request.user)
    # Someone who replied while the ticket was public must not keep reading it
    if ticket.is_private:
        previous_messages = previous_messages.filter(sender__is_staff=True)
    previous_senders = previous_messages.values_list("sender__email", flat=True).distinct()

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


@ticket_api.post("/{ticket_id}/upvote", response={200: TicketDetailSchema, 400: message_response})
def upvote_ticket(
    request: AuthenticatedHttpRequest, ticket_id: int
) -> tuple[int, Ticket | dict[str, str]]:
    """Say a ticket matters to you too. Upvoting twice counts once."""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
    if ticket.created_by == request.user:
        return 400, {"message": "You can't upvote your own ticket"}
    if ticket.is_private:
        return 400, {"message": "A private ticket can't be upvoted"}

    ticket.upvoters.add(request.user)
    return 200, visible_tickets(request.user).get(id=ticket.id)


@ticket_api.delete("/{ticket_id}/upvote", response={200: TicketDetailSchema})
def remove_upvote(request: AuthenticatedHttpRequest, ticket_id: int) -> tuple[int, Ticket]:
    """Take an upvote back. Doing so without one is not an error."""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
    ticket.upvoters.remove(request.user)
    return 200, visible_tickets(request.user).get(id=ticket.id)
