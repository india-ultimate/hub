"""Who may read members-only announcements, in the app and in email."""

from django.db.models import OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from server.core.models import Player, User
from server.subscription.models import Subscription
from server.utils import today


def can_read_members_only(user: User) -> bool:
    """Staff, and anyone with an active membership, read members-only posts."""
    if user.is_staff:
        return True
    try:
        player = user.player_profile
    except Player.DoesNotExist:
        return False
    # Same rule as /api/me/subscription, which the dashboard shows.
    subscription = player.current_subscription
    return subscription is not None and subscription.is_active


def members_only_readers(users: QuerySet[User]) -> QuerySet[User]:
    """The users can_read_members_only lets in, worked out in one query.

    Mirrors Player.current_subscription: this season's subscription, else the
    earliest one already bought for a later season.
    """
    player = OuterRef("player_profile")
    current = Subscription.objects.current().filter(player=player).values("is_active")[:1]
    upcoming = (
        Subscription.objects.live()
        .filter(player=player, start_date__gt=today())
        .order_by("start_date")
        .values("is_active")[:1]
    )
    return users.annotate(membership_active=Coalesce(Subquery(current), Subquery(upcoming))).filter(
        Q(is_staff=True) | Q(membership_active=True)
    )
