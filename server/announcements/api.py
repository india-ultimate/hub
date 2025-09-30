from django.http import HttpRequest
from ninja import Router

from server.announcements.models import Announcement
from server.announcements.schema import AnnouncementSchema

# Create announcements router
router = Router()


@router.get("/", response={200: list[AnnouncementSchema]})
def get_announcements(request: HttpRequest) -> list[Announcement]:
    """Get all announcements (published for public, all for staff)"""
    if hasattr(request, "user") and request.user.is_authenticated and request.user.is_staff:
        # Staff users see all announcements including drafts
        return list(Announcement.objects.select_related("author").order_by("-created_at"))
    else:
        # Public users see only published announcements
        return list(
            Announcement.objects.filter(is_published=True)
            .select_related("author")
            .order_by("-created_at")
        )


@router.get("/{slug}", response={200: AnnouncementSchema, 404: dict[str, str]})
def get_announcement_detail(
    request: HttpRequest, slug: str
) -> Announcement | tuple[int, dict[str, str]]:
    """Get a single announcement by slug. Staff can view drafts; public only published."""
    qs = Announcement.objects.select_related("author").filter(slug=slug)
    if hasattr(request, "user") and request.user.is_authenticated and request.user.is_staff:
        announcement = qs.first()
    else:
        announcement = qs.filter(is_published=True).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    return announcement
