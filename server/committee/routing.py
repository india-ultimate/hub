"""Which committees a ticket goes to, and who they are."""

from django.db.models import QuerySet

from server.committee.models import Committee, Role
from server.core.models import User


def committees_for(category: str | None) -> QuerySet[Committee]:
    """The committees that handle tickets of `category`. None: a join on a null
    category would match every committee without a route."""
    if not category:
        return Committee.objects.none()
    return Committee.objects.filter(routes__category__key=category)


def chairs_for(category: str | None) -> QuerySet[User]:
    """The current chairs of every committee `category` routes to."""
    chairs = Role.objects.current().filter(is_chair=True, committee__in=committees_for(category))
    return User.objects.filter(committee_roles__in=chairs).distinct()


def members_for(category: str | None) -> QuerySet[User]:
    """Everyone with a current role in a committee `category` routes to."""
    roles = Role.objects.current().filter(committee__in=committees_for(category))
    return User.objects.filter(committee_roles__in=roles).distinct()


def committees_of(user: User) -> QuerySet[Committee]:
    """The committees where `user` holds a current role."""
    return Committee.objects.filter(roles__in=Role.objects.current().filter(user=user)).distinct()
