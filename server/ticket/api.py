import logging
import os
import re
from collections.abc import Iterable
from typing import Any, Literal
from urllib.parse import unquote, urlparse

import cloudinary
import cloudinary.uploader
from django.conf import settings
from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from ninja import Router
from ninja.files import UploadedFile
from ninja.pagination import PageNumberPagination, paginate
from ninja.params.functions import File, Query

from server.committee.models import Committee, TicketRoute
from server.committee.routing import chairs_for
from server.core.models import User
from server.ticket.access import can_be_assigned, can_handle, handlers, routed_to
from server.ticket.models import Ticket, TicketCategory, TicketMessage
from server.ticket.schema import (
    TicketCategoryCreateSchema,
    TicketCategorySchema,
    TicketCategoryUpdateSchema,
    TicketCreateSchema,
    TicketDetailSchema,
    TicketListItemSchema,
    TicketMessageCreateSchema,
    TicketMessageEditSchema,
    TicketRouteSchema,
    TicketRouteUpdateSchema,
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


logger = logging.getLogger(__name__)
ticket_api = Router()


Status = Literal["OPN", "PRG", "RES"]
Sort = Literal["relevance", "newest", "upvotes"]
PAGE_SIZE = 20
DUPLICATE_NAME = "A category with that name already exists"
MAX_ORDER = 32767  # what a PositiveSmallIntegerField holds
TITLE_MAX_LENGTH = 200


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
    """The tickets `user` may see: a private one only to its creator, staff and
    the committees its category routes to.

    Each comes with its upvote count and whether `user` is one of them.
    """
    upvotes = Ticket.upvoters.through.objects.filter(ticket=OuterRef("pk"))
    tickets = (
        Ticket.objects.annotate(
            upvote_count=_count(upvotes),
            has_upvoted=Exists(upvotes.filter(user=user)),
        )
        .select_related("category", "created_by")
        .prefetch_related("assignees__player_profile")
    )
    if user.is_staff:
        return tickets
    return tickets.filter(Q(is_private=False) | Q(created_by=user) | routed_to(user))


def _notify_assigned(ticket: Ticket, users: Iterable[User]) -> None:
    """Email each of `users` that the ticket is theirs to handle."""
    recipients = [user.email for user in users if user.email]
    if not recipients:
        return
    try:
        plain_message = f"Ticket #{ticket.id} has been assigned to you:\n\n"
        plain_message += f"{ticket.title}\n"
        plain_message += f"Priority: {ticket.get_priority_display()}\n\n"
        plain_message += "You can view and respond to this ticket on the website."
        context = {"ticket": ticket, "site_url": settings.PUBLIC_URL}
        send_mail(
            subject=f"Ticket #{ticket.id} assigned to you: {ticket.title}",
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=recipients,
            fail_silently=True,
            html_message=render_to_string("emails/ticket_assigned.html", context),
        )
    except Exception as e:
        # Log the error but don't fail the request
        print(f"Error sending email notification: {e}")


def _deny_unless_staff(request: AuthenticatedHttpRequest) -> tuple[int, dict[str, str]] | None:
    if request.user.is_staff:
        return None
    return 403, {"message": "Only staff can do this"}


@ticket_api.get("/categories", response={200: list[TicketCategorySchema], 403: message_response})
def list_categories(request: AuthenticatedHttpRequest, all: bool = False) -> tuple[int, Any]:
    """The categories a ticket can have, in order. Staff can ask for all of them:
    the retired ones come after the active ones."""
    categories = TicketCategory.objects.order_by("is_retired", "order", "name")
    if not all:
        return 200, categories.filter(is_retired=False)
    return _deny_unless_staff(request) or (200, categories)


def _name_error(name: str, category: TicketCategory | None = None) -> str | None:
    """Why `name` can't be a category's name, if it can't."""
    if not name:
        return "A category needs a name"
    if len(name) > TicketCategory.NAME_MAX_LENGTH:
        return "That name is too long"
    taken = TicketCategory.objects.filter(name__iexact=name)
    if category:
        taken = taken.exclude(pk=category.pk)
    if taken.exists():
        return DUPLICATE_NAME
    return None


@ticket_api.post(
    "/categories",
    response={201: TicketCategorySchema, 400: message_response, 403: message_response},
)
def create_category(
    request: AuthenticatedHttpRequest, data: TicketCategoryCreateSchema
) -> tuple[int, Any]:
    """Add a category, last in the order. Staff only."""
    if denied := _deny_unless_staff(request):
        return denied
    name = data.name.strip()
    if error := _name_error(name):
        return 400, {"message": error}
    last = TicketCategory.objects.order_by("-order").first()
    try:
        with transaction.atomic():
            category = TicketCategory.objects.create(
                key=TicketCategory.new_key(name),
                name=name,
                order=min(last.order + 1, MAX_ORDER) if last else 0,
            )
    except IntegrityError:  # someone added the same name or key meanwhile
        return 400, {"message": DUPLICATE_NAME}
    return 201, category


@ticket_api.put(
    "/categories/{key}",
    response={
        200: TicketCategorySchema,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def update_category(
    request: AuthenticatedHttpRequest, key: str, data: TicketCategoryUpdateSchema
) -> tuple[int, Any]:
    """Rename, reorder, retire or restore a category. The key never changes. Staff only."""
    if denied := _deny_unless_staff(request):
        return denied
    category = get_object_or_404(TicketCategory, key=key)
    if data.name is not None:
        name = data.name.strip()
        if error := _name_error(name, category):
            return 400, {"message": error}
        category.name = name
    if data.order is not None:
        if not 0 <= data.order <= MAX_ORDER:
            return 400, {"message": f"The order must be between 0 and {MAX_ORDER}"}
        category.order = data.order
    if data.is_retired is not None:
        category.is_retired = data.is_retired
    try:
        with transaction.atomic():
            category.save()
    except IntegrityError:  # someone took the name meanwhile
        return 400, {"message": DUPLICATE_NAME}
    return 200, category


def _category_error(key: str | None, current: str | None = None) -> str | None:
    """Why a ticket can't be given the category `key`, if it can't. Keeping the
    `current` one is always fine, even once retired."""
    if not key or key == current:
        return None
    if not TicketCategory.objects.filter(key=key, is_retired=False).exists():
        return "That category doesn't exist"
    return None


@ticket_api.get("/routes", response={200: list[TicketRouteSchema], 403: message_response})
def list_routes(request: AuthenticatedHttpRequest) -> tuple[int, Any]:
    """Which committees each category of ticket goes to, retired categories too.
    Staff only."""
    if denied := _deny_unless_staff(request):
        return denied
    routes = TicketRoute.objects.order_by("committee__order", "committee__name")
    by_category: dict[str, list[str]] = {
        key: [] for key in TicketCategory.objects.values_list("key", flat=True)
    }
    for route in routes.select_related("committee"):
        by_category[route.category_id].append(route.committee.slug)
    return 200, [{"category": c, "committees": slugs} for c, slugs in by_category.items()]


@ticket_api.put(
    "/routes/{category}",
    response={
        200: TicketRouteSchema,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def update_route(
    request: AuthenticatedHttpRequest, category: str, data: TicketRouteUpdateSchema
) -> tuple[int, Any]:
    """Replace the committees that new tickets of `category` go to. Staff only."""
    if denied := _deny_unless_staff(request):
        return denied
    category_row = get_object_or_404(TicketCategory, key=category)
    committees = Committee.objects.filter(slug__in=data.committees).order_by("order", "name")
    if committees.count() != len(set(data.committees)):
        return 400, {"message": "Unknown committee"}
    with transaction.atomic():
        TicketRoute.objects.filter(category=category_row).delete()
        TicketRoute.objects.bulk_create(
            TicketRoute(category=category_row, committee=committee) for committee in committees
        )
    return 200, {"category": category, "committees": [c.slug for c in committees]}


@ticket_api.get("/", response=list[TicketListItemSchema])
@paginate(PageNumberPagination, page_size=PAGE_SIZE)
def list_tickets(
    request: AuthenticatedHttpRequest,
    q: str = "",
    status: list[Status] = Query(None),  # noqa: B008  # repeatable: ?status=OPN&status=PRG
    category: str | None = None,
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
        message_count=_count(TicketMessage.objects.filter(ticket=OuterRef("pk"), is_deleted=False))
    )
    if status:
        query = query.filter(status__in=status)
    if category:
        query = query.filter(category__key=category)
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


@ticket_api.post("/", response={201: TicketDetailSchema, 400: message_response})
def create_ticket(
    request: AuthenticatedHttpRequest, data: TicketCreateSchema
) -> tuple[int, Ticket | dict[str, str]]:
    """Create a new ticket"""
    if error := _category_error(data.category):
        return 400, {"message": error}
    ticket = Ticket.objects.create(
        title=data.title,
        description=data.description,
        priority=data.priority,
        category_id=data.category,
        is_private=data.is_private,
        created_by=request.user,
    )
    chairs = list(chairs_for(ticket.category_id))
    ticket.assignees.set(chairs)
    _notify_assigned(ticket, chairs)

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
                "site_url": settings.PUBLIC_URL,
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


@ticket_api.put(
    "/{ticket_id}",
    response={200: TicketDetailSchema, 400: message_response, 403: message_response},
)
def update_ticket(
    request: AuthenticatedHttpRequest, ticket_id: int, data: TicketUpdateSchema
) -> tuple[int, Ticket | dict[str, Any]]:
    """Update ticket details"""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)

    is_creator = ticket.created_by == request.user
    is_handler = can_handle(request.user, ticket)
    if not (is_creator or is_handler):
        return 403, {"message": "You don't have permission to update this ticket"}

    if request.user.is_staff and (error := _category_error(data.category, ticket.category_id)):
        return 400, {"message": error}

    # The creator and staff can fix the title and description
    if is_creator or request.user.is_staff:
        for field in ("title", "description"):
            if getattr(data, field) is None:
                continue
            value = getattr(data, field).strip()
            if not value:
                return 400, {"message": f"The {field} can't be empty"}
            if field == "title" and len(value) > TITLE_MAX_LENGTH:
                return 400, {"message": f"The title can be at most {TITLE_MAX_LENGTH} characters"}
            if value != getattr(ticket, field):
                setattr(ticket, field, value)
                ticket.edited_at = timezone.now()

    # The creator and the handlers can set the status; handlers also the priority,
    # and only staff the category
    if data.status:
        ticket.status = data.status
    if is_handler and data.priority:
        ticket.priority = data.priority
    if request.user.is_staff and data.category:
        ticket.category_id = data.category

    # Both the creator and staff can hide a ticket, or show it again
    if data.is_private is not None and (is_creator or request.user.is_staff):
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

    # Add the assignees, but a private ticket only goes to those who can open it
    assignees = ticket.assignees.exclude(id=request.user.id)
    if ticket.is_private:
        assignees = assignees.filter(id__in=handlers(ticket).values("id"))
    recipients.update(email for email in assignees.values_list("email", flat=True) if email)

    # Add all users who have previously sent messages (except the current sender)
    previous_messages = TicketMessage.objects.filter(ticket=ticket).exclude(sender=request.user)
    # Someone who replied while the ticket was public must not keep reading it
    if ticket.is_private:
        previous_messages = previous_messages.filter(sender__in=handlers(ticket))
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
                "site_url": settings.PUBLIC_URL,
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


def _reply(
    request: AuthenticatedHttpRequest, ticket_id: int, message_id: int
) -> tuple[Ticket, TicketMessage]:
    """A reply that isn't deleted, on a ticket the user can see, or a 404."""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
    message = get_object_or_404(TicketMessage, id=message_id, ticket=ticket, is_deleted=False)
    return ticket, message


def _destroy_attachment(url: str) -> None:
    """Remove a deleted reply's upload from Cloudinary. The reply is gone either
    way, so a failure is only logged."""
    match = re.search(r"/(image|video|raw)/upload/(?:v\d+/)?(.+)$", unquote(urlparse(url).path))
    if not match:
        return
    kind, public_id = match.groups()
    if kind != "raw":  # images and videos are named without their extension
        public_id = os.path.splitext(public_id)[0]
    try:
        cloudinary.uploader.destroy(public_id, resource_type=kind, invalidate=True)
    except Exception:
        logger.exception("Couldn't delete the ticket attachment %s", url)


@ticket_api.patch(
    "/{ticket_id}/message/{message_id}",
    response={200: TicketDetailSchema, 400: message_response, 403: message_response},
)
def edit_message(
    request: AuthenticatedHttpRequest,
    ticket_id: int,
    message_id: int,
    data: TicketMessageEditSchema,
) -> tuple[int, Ticket | dict[str, str]]:
    """Fix your own reply. No one is emailed again: their copy stays as sent."""
    ticket, message = _reply(request, ticket_id, message_id)
    if message.sender_id != request.user.id:
        return 403, {"message": "You can only edit your own replies"}
    text = data.message.strip()
    if not text:
        return 400, {"message": "A reply can't be empty"}
    if text != message.message.strip():
        message.message, message.edited_at = text, timezone.now()
        message.save(update_fields=["message", "edited_at"])
    return 200, ticket


@ticket_api.delete(
    "/{ticket_id}/message/{message_id}",
    response={200: TicketDetailSchema, 403: message_response},
)
def delete_message(
    request: AuthenticatedHttpRequest, ticket_id: int, message_id: int
) -> tuple[int, Ticket | dict[str, str]]:
    """Take back a reply, or for staff remove anyone's. It leaves a placeholder,
    so the conversation still reads."""
    ticket, message = _reply(request, ticket_id, message_id)
    if message.sender_id != request.user.id and not request.user.is_staff:
        return 403, {"message": "You can only delete your own replies"}
    attachment = message.attachment
    message.is_deleted, message.message, message.attachment = True, "", None
    message.save(update_fields=["is_deleted", "message", "attachment"])
    if attachment:
        _destroy_attachment(attachment)
    return 200, ticket


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


@ticket_api.post(
    "/{ticket_id}/assignees/{user_id}",
    response={200: TicketDetailSchema, 400: message_response, 403: message_response},
)
def add_assignee(
    request: AuthenticatedHttpRequest, ticket_id: int, user_id: int
) -> tuple[int, Ticket | dict[str, str]]:
    """Make someone responsible for a ticket, and tell them unless it was you."""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
    if not can_handle(request.user, ticket):
        return 403, {"message": "You can't change who handles this ticket"}
    assignee = get_object_or_404(User, id=user_id)
    if not can_be_assigned(assignee):
        return 400, {"message": "Only staff and committee members can be assigned"}
    if not ticket.assignees.filter(id=assignee.id).exists():
        ticket.assignees.add(assignee)
        if assignee != request.user:
            _notify_assigned(ticket, [assignee])
    return 200, visible_tickets(request.user).get(id=ticket.id)


@ticket_api.delete(
    "/{ticket_id}/assignees/{user_id}", response={200: TicketDetailSchema, 403: message_response}
)
def remove_assignee(
    request: AuthenticatedHttpRequest, ticket_id: int, user_id: int
) -> tuple[int, Ticket | dict[str, str]]:
    """Take someone off a ticket. Removing someone not on it is not an error."""
    ticket = get_object_or_404(visible_tickets(request.user), id=ticket_id)
    if not can_handle(request.user, ticket):
        return 403, {"message": "You can't change who handles this ticket"}
    ticket.assignees.remove(user_id)
    return 200, visible_tickets(request.user).get(id=ticket.id)
