from ninja import ModelSchema

from server.announcements.models import Announcement
from server.core.models import User
from server.schema import UserMinSchema


def _can_read(announcement: Announcement) -> bool:
    # Set by the API's queryset; missing means locked.
    return bool(getattr(announcement, "can_read", False))


class AnnouncementSchema(ModelSchema):
    author: UserMinSchema
    author_profile_pic_url: str | None = None
    can_read: bool

    @staticmethod
    def resolve_author(announcement: Announcement) -> User:
        return announcement.author

    @staticmethod
    def resolve_author_profile_pic_url(announcement: Announcement) -> str | None:
        try:
            return announcement.author.player_profile.profile_pic_url
        except Exception:
            return None

    @staticmethod
    def resolve_can_read(announcement: Announcement) -> bool:
        return _can_read(announcement)

    # Members-only posts reach non-members with only the title and metadata.
    @staticmethod
    def resolve_content(announcement: Announcement) -> str:
        return announcement.content if _can_read(announcement) else ""

    @staticmethod
    def resolve_action_text(announcement: Announcement) -> str | None:
        return announcement.action_text if _can_read(announcement) else None

    @staticmethod
    def resolve_action_url(announcement: Announcement) -> str | None:
        return announcement.action_url if _can_read(announcement) else None

    class Meta:
        model = Announcement
        fields = "__all__"
