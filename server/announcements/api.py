from django.db.models import BooleanField, Case, QuerySet, Value, When
from django.http import HttpRequest
from ninja import Router

from server.announcements.models import Announcement
from server.announcements.schema import AnnouncementSchema
from server.core.models import Player, User

# Create announcements router
router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


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


def _with_access(request: AuthenticatedHttpRequest) -> QuerySet[Announcement]:
    """Announcements this user may see, annotated with whether they can read each."""
    qs = Announcement.objects.select_related("author", "author__player_profile")
    if not request.user.is_staff:
        # Public users see only published announcements
        qs = qs.filter(is_published=True)
    return qs.annotate(
        can_read=Case(
            When(is_members_only=False, then=Value(True)),
            default=Value(can_read_members_only(request.user)),
            output_field=BooleanField(),
        )
    )


@router.get("/", response={200: list[AnnouncementSchema]})
def get_announcements(request: AuthenticatedHttpRequest) -> list[Announcement]:
    """Get all announcements (published for public, all for staff)"""
    return list(_with_access(request).order_by("-created_at"))


@router.get("/{slug}", response={200: AnnouncementSchema, 404: dict[str, str]})
def get_announcement_detail(
    request: AuthenticatedHttpRequest, slug: str
) -> Announcement | tuple[int, dict[str, str]]:
    """Get a single announcement by slug. Staff can view drafts; public only published."""
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    return announcement
