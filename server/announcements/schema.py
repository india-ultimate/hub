from ninja import ModelSchema

from server.announcements.models import Announcement
from server.core.models import User
from server.schema import UserMinSchema


class AnnouncementSchema(ModelSchema):
    author: UserMinSchema
    author_profile_pic_url: str | None

    @staticmethod
    def resolve_author(announcement: Announcement) -> User:
        return announcement.author

    @staticmethod
    def resolve_author_profile_pic_url(announcement: Announcement) -> str | None:
        try:
            return announcement.author.player_profile.profile_pic_url
        except Exception:
            return None

    class Config:
        model = Announcement
        model_fields = "__all__"
