"""Who may handle a ticket: staff, and the committees its category routes to."""

from django.db.models import Q, QuerySet

from server.committee.models import Role
from server.committee.routing import committees_for, committees_of, members_for
from server.core.models import User
from server.ticket.models import Ticket


def routed_to(user: User) -> Q:
    """Tickets whose category routes to one of the committees `user` holds a role in."""
    return Q(category__in=committees_of(user).values("routes__category"))


def can_handle(user: User, ticket: Ticket) -> bool:
    """Staff, and members of the committees the ticket's category routes to."""
    return (
        user.is_staff
        or committees_for(ticket.category).filter(pk__in=committees_of(user).values("pk")).exists()
    )


def handlers(ticket: Ticket) -> QuerySet[User]:
    """Everyone who can open a private ticket, besides its creator."""
    return User.objects.filter(
        Q(is_staff=True) | Q(pk__in=members_for(ticket.category).values("pk"))
    )


def can_be_assigned(user: User) -> bool:
    return user.is_staff or Role.objects.current().filter(user=user).exists()
