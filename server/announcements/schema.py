from typing import Any, Literal

from ninja import ModelSchema, Schema

from server.announcements.access import can_manage
from server.announcements.models import Announcement, Comment
from server.core.models import User
from server.schema import UserNameSchema, profile_pic_url


def _can_read(announcement: Announcement) -> bool:
    # Set by the API's queryset; missing means locked.
    return bool(getattr(announcement, "can_read", False))


class ReactionCountSchema(Schema):
    kind: str
    count: int
    reacted: bool


class AnnouncementSchema(ModelSchema):
    author: UserNameSchema
    author_profile_pic_url: str | None = None
    can_read: bool
    comment_count: int
    reactions: list[ReactionCountSchema]
    can_manage: bool

    @staticmethod
    def resolve_can_manage(announcement: Announcement, context: dict[str, Any]) -> bool:
        return can_manage(context["request"].user, announcement)

    @staticmethod
    def resolve_author(announcement: Announcement) -> User:
        return announcement.author

    @staticmethod
    def resolve_author_profile_pic_url(announcement: Announcement) -> str | None:
        return profile_pic_url(announcement.author)

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

    # Set by the API's queryset and view, like can_read.
    @staticmethod
    def resolve_comment_count(announcement: Announcement) -> int:
        return getattr(announcement, "comment_count", 0) if _can_read(announcement) else 0

    @staticmethod
    def resolve_reactions(announcement: Announcement) -> list[dict[str, Any]]:
        return getattr(announcement, "reaction_counts", []) if _can_read(announcement) else []

    class Meta:
        model = Announcement
        fields = "__all__"


class AnnouncementInSchema(Schema):
    title: str
    content: str
    type: Announcement.Type = Announcement.Type.COMPETITIONS
    is_members_only: bool = False
    is_published: bool = False
    allow_comments: bool = True
    action_text: str = ""
    action_url: str = ""


class AnnouncementUpdateSchema(Schema):
    """Whatever is sent changes; null, like leaving it out, keeps what's there.
    Send "" to clear the action button."""

    title: str | None = None
    content: str | None = None
    type: Announcement.Type | None = None
    is_members_only: bool | None = None
    is_published: bool | None = None
    allow_comments: bool | None = None
    action_text: str | None = None
    action_url: str | None = None


class ImageSchema(Schema):
    url: str


class VideoUploadSchema(Schema):
    """Where the browser sends a video, and the form fields to send with it."""

    url: str
    fields: dict[str, str]


class UploadedVideoSchema(Schema):
    secure_url: str  # Cloudinary's name for it, so both uploads answer alike


class QueuedSchema(Schema):
    queued: int


class EmailInSchema(Schema):
    audience: Literal["all", "members"]


class CommentSchema(ModelSchema):
    author: UserNameSchema
    author_profile_pic_url: str | None = None
    author_is_staff: bool
    can_delete: bool
    reactions: list[ReactionCountSchema]
    replies: list["CommentSchema"]

    @staticmethod
    def resolve_author_profile_pic_url(comment: Comment) -> str | None:
        return profile_pic_url(comment.author)

    @staticmethod
    def resolve_author_is_staff(comment: Comment) -> bool:
        return comment.author.is_staff

    @staticmethod
    def resolve_can_delete(comment: Comment, context: dict[str, Any]) -> bool:
        user = context["request"].user
        return not comment.is_deleted and (comment.author_id == user.id or user.is_staff)

    # Set by the view, as on an announcement; a deleted comment shows none.
    @staticmethod
    def resolve_reactions(comment: Comment) -> list[dict[str, Any]]:
        return [] if comment.is_deleted else getattr(comment, "reaction_counts", [])

    @staticmethod
    def resolve_replies(comment: Comment) -> Any:
        # The manager, not .all(): ninja may pass a getter that has listed it already.
        return [] if comment.parent_id else comment.replies

    class Meta:
        model = Comment
        fields = ["id", "body", "is_deleted", "created_at"]


class CommentCreateSchema(Schema):
    body: str
    parent_id: int | None = None


class AnnouncementHeadlineSchema(ModelSchema):
    class Meta:
        model = Announcement
        fields = ["title", "slug", "type", "is_members_only", "created_at"]
