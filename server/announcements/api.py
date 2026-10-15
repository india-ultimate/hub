import os
import time
import unicodedata
import uuid
from collections.abc import Iterable
from typing import Any

import cloudinary
import cloudinary.utils
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import BooleanField, Case, Count, Prefetch, Q, QuerySet, Value, When
from django.http import HttpRequest
from django.utils.text import slugify
from ninja import Router, UploadedFile
from ninja.params.functions import File
from ninja.throttling import AuthRateThrottle
from PIL import Image

from server.announcements.access import can_manage, can_post, can_read_members_only
from server.announcements.cleaning import clean_content, is_blank
from server.announcements.emails import (
    send_announcement_to_all_users,
    send_announcement_to_email,
    send_announcement_to_members,
)
from server.announcements.models import Announcement, Comment, CommentReaction, Reaction
from server.announcements.schema import (
    AnnouncementInSchema,
    AnnouncementSchema,
    AnnouncementUpdateSchema,
    CommentCreateSchema,
    CommentSchema,
    EmailInSchema,
    ImageSchema,
    QueuedSchema,
    ReactionCountSchema,
    UploadedVideoSchema,
    VideoUploadSchema,
    _can_read,
)
from server.core.models import User
from server.storage.ckeditor import upload_error
from server.storage.cloudinary import CloudinaryStorage

# Create announcements router
router = Router()

Message = dict[str, str]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
TITLE_MAX_LENGTH = 200
ACTION_TEXT_MAX_LENGTH = 100
KIND_ORDER = {kind: i for i, kind in enumerate(Reaction.Kind.values)}


def _limit(scope: str, rate: str) -> AuthRateThrottle:
    """A per-user limit counted apart from the others: AuthRateThrottles all
    share the "auth" scope, so one would eat into another's count."""
    throttle = AuthRateThrottle(rate)
    throttle.scope = scope
    return throttle


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _with_access(request: AuthenticatedHttpRequest) -> QuerySet[Announcement]:
    """Announcements this user may see, annotated with whether they can read each."""
    qs = Announcement.objects.select_related("author", "author__player_profile")
    # A poster's own posts; for anyone else, a condition nothing meets
    mine = Q(author=request.user) if can_post(request.user) else Q(pk__in=[])
    if not request.user.is_staff:
        # Public users see only published announcements, and posters their own drafts
        qs = qs.filter(Q(is_published=True) | mine)
    return qs.annotate(
        can_read=Case(
            When(Q(is_members_only=False) | mine, then=Value(True)),
            default=Value(can_read_members_only(request.user)),
            output_field=BooleanField(),
        ),
        comment_count=Count("comments", filter=Q(comments__is_deleted=False)),
    )


def _counts_by(key: str, reactions: QuerySet[Any], user: User) -> dict[int, list[dict[str, Any]]]:
    """Reactions grouped by what they're on (`key`), in Kind order: how many,
    and whether this user gave one."""
    rows = reactions.values(key, "kind").annotate(
        count=Count("id"), mine=Count("id", filter=Q(user=user))
    )
    counts: dict[int, list[dict[str, Any]]] = {}
    for row in sorted(rows, key=lambda row: KIND_ORDER[row["kind"]]):
        counts.setdefault(row[key], []).append(
            {"kind": row["kind"], "count": row["count"], "reacted": row["mine"] > 0}
        )
    return counts


def _reaction_counts(
    user: User, announcement_ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    reactions = Reaction.objects.filter(announcement_id__in=announcement_ids)
    return _counts_by("announcement_id", reactions, user)


def _comment_reaction_counts(
    user: User, comment_ids: Iterable[int]
) -> dict[int, list[dict[str, Any]]]:
    reactions = CommentReaction.objects.filter(comment_id__in=comment_ids)
    return _counts_by("comment_id", reactions, user)


def _with_reactions(user: User, announcements: list[Announcement]) -> list[Announcement]:
    """Attach the reactions, in one query for all of them, for AnnouncementSchema."""
    counts = _reaction_counts(user, [a.id for a in announcements])
    for announcement in announcements:
        announcement.reaction_counts = counts.get(announcement.id, [])  # type: ignore[attr-defined]
    return announcements


def _with_comment_reactions(user: User, comments: list[Comment]) -> list[Comment]:
    """Attach every comment's and reply's reactions, in one query, for CommentSchema."""
    everyone = [c for comment in comments for c in (comment, *comment.replies.all())]
    counts = _comment_reaction_counts(user, [c.id for c in everyone])
    for comment in everyone:
        comment.reaction_counts = counts.get(comment.id, [])  # type: ignore[attr-defined]
    return comments


def _readable(request: AuthenticatedHttpRequest, slug: str) -> Announcement | tuple[int, Message]:
    """The announcement, or the 404 or 403 every comment and reaction endpoint returns."""
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    if not _can_read(announcement):
        return 403, {"message": "This announcement is for members only."}
    return announcement


def _image_error(file: UploadedFile) -> str:
    """Why this upload can't go in an announcement, or "". It must be a photo, not
    something the browser would run."""
    if os.path.splitext(file.name or "")[1].lower() not in IMAGE_EXTENSIONS:
        return "Upload a JPG, PNG, GIF or WebP image."
    if error := upload_error(file):
        return error
    try:
        with Image.open(file) as image:
            image.verify()
    except Exception:
        return "That file isn't an image."
    finally:
        file.seek(0)
    return ""


@router.post(
    "/images",
    response={200: ImageSchema, 400: Message, 403: Message},
    throttle=_limit("announcement_image", "30/m"),
)
def upload_image(
    request: AuthenticatedHttpRequest,
    file: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, ImageSchema | Message]:
    """A picture for an announcement's body. Declared before the routes that take a
    slug, which would otherwise answer for "images"."""
    if not can_post(request.user):
        return 403, {"message": "You can't post announcements."}
    if error := _image_error(file):
        return 400, {"message": error}
    extension = os.path.splitext(file.name or "")[1].lower()
    name = default_storage.save(f"announcement_images/{uuid.uuid4().hex}{extension}", file)
    return 200, ImageSchema(url=default_storage.url(name))


VIDEO_FORMATS = ("mp4", "webm", "mov")


@router.post(
    "/videos",
    response={200: VideoUploadSchema, 403: Message},
    throttle=_limit("announcement_video", "10/m"),
)
def start_video_upload(
    request: AuthenticatedHttpRequest,
) -> tuple[int, VideoUploadSchema | Message]:
    """A signed upload for one video, which the browser sends straight to Cloudinary:
    videos are too big to pass through the Hub's machines. Without Cloudinary (in
    development), the Hub keeps them itself."""
    if not can_post(request.user):
        return 403, {"message": "You can't post announcements."}
    if not isinstance(default_storage, CloudinaryStorage):
        return 200, VideoUploadSchema(url="/api/announcements/videos/file", fields={})
    fields = {
        "public_id": f"{settings.CLOUDINARY_MEDIA_PREFIX}announcement_videos/{uuid.uuid4().hex}",
        "allowed_formats": ",".join(VIDEO_FORMATS),
        "format": "mp4",  # what every browser plays; a Mac's recordings are .mov
        "overwrite": "false",  # or the signature, good for an hour, could replace a video
        "timestamp": str(int(time.time())),
    }
    config = cloudinary.config()
    fields["signature"] = cloudinary.utils.api_sign_request(fields, config.api_secret)
    fields["api_key"] = config.api_key
    url = f"https://api.cloudinary.com/v1_1/{config.cloud_name}/video/upload"
    return 200, VideoUploadSchema(url=url, fields=fields)


@router.post(
    "/videos/file",
    response={200: UploadedVideoSchema, 400: Message, 403: Message, 404: Message},
    throttle=_limit("announcement_video", "10/m"),
)
def upload_video_here(
    request: AuthenticatedHttpRequest,
    file: UploadedFile = File(...),  # noqa: B008
) -> tuple[int, UploadedVideoSchema | Message]:
    """Development only: with Cloudinary, videos go straight there."""
    if isinstance(default_storage, CloudinaryStorage):
        return 404, {"message": "Upload videos to Cloudinary."}
    if not can_post(request.user):
        return 403, {"message": "You can't post announcements."}
    extension = os.path.splitext(file.name or "")[1].lower()
    if extension.lstrip(".") not in VIDEO_FORMATS:
        return 400, {"message": "Upload an MP4, WebM or MOV video."}
    name = default_storage.save(f"announcement_videos/{uuid.uuid4().hex}{extension}", file)
    return 200, UploadedVideoSchema(secure_url=default_storage.url(name))


@router.get("/", response={200: list[AnnouncementSchema]})
def get_announcements(request: AuthenticatedHttpRequest) -> list[Announcement]:
    """Get all announcements (published for public, all for staff)"""
    return _with_reactions(request.user, list(_with_access(request).order_by("-created_at")))


@router.get("/{slug}", response={200: AnnouncementSchema, 404: Message})
def get_announcement_detail(
    request: AuthenticatedHttpRequest, slug: str
) -> Announcement | tuple[int, Message]:
    """Get a single announcement by slug. Staff can view drafts; public only published."""
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    return _with_reactions(request.user, [announcement])[0]


def _with_details(request: AuthenticatedHttpRequest, announcement: Announcement) -> Announcement:
    """The announcement as the list shows it, for AnnouncementSchema."""
    return _with_reactions(request.user, [_with_access(request).get(pk=announcement.pk)])[0]


def _problem(announcement: Announcement, changed: Iterable[str]) -> str:
    """What's wrong with the fields being saved, or "". The others are left
    alone, so an old post the editor can't keep can still be retitled or published."""
    changed = set(changed)
    if "title" in changed:
        title = announcement.title
        if not 1 <= len(title) <= TITLE_MAX_LENGTH:
            return f"The title must be 1 to {TITLE_MAX_LENGTH} characters."
        # A control character would break the email's subject line
        if any(unicodedata.category(char) == "Cc" for char in title):
            return "The title can't contain line breaks or control characters."
        if not slugify(title):  # no slug, no address for the post
            return "Give the announcement a title with letters or numbers."
    if "content" in changed and is_blank(announcement.content):
        return "The announcement can't be empty."
    if "action_text" in changed and len(announcement.action_text or "") > ACTION_TEXT_MAX_LENGTH:
        return f"The button text can be at most {ACTION_TEXT_MAX_LENGTH} characters."
    if changed & {"action_text", "action_url"}:
        if announcement.action_text and not announcement.action_url:
            return "A button needs a link."
        try:
            if announcement.action_url:
                URLValidator(schemes=["http", "https"])(announcement.action_url)
        except ValidationError:
            return "The button link must be an http or https address."
    return ""


def _apply(announcement: Announcement, changes: dict[str, Any]) -> str:
    """Set the changes, tidied, on the announcement. Returns what's wrong, or ""."""
    for field, value in changes.items():
        setattr(announcement, field, value.strip() if isinstance(value, str) else value)
    if "content" in changes:  # old posts keep what the Hub editor can't, until edited
        announcement.content = clean_content(announcement.content)
    return _problem(announcement, changes)


@router.post(
    "/",
    response={201: AnnouncementSchema, 400: Message, 403: Message},
    throttle=_limit("announcement_write", "30/m"),
)
def create_announcement(
    request: AuthenticatedHttpRequest, payload: AnnouncementInSchema
) -> tuple[int, Announcement | Message]:
    if not can_post(request.user):
        return 403, {"message": "You can't post announcements."}
    announcement = Announcement(author=request.user)
    if problem := _apply(announcement, payload.dict()):
        return 400, {"message": problem}
    announcement.save()
    return 201, _with_details(request, announcement)


@router.put(
    "/{slug}",
    response={200: AnnouncementSchema, 400: Message, 403: Message, 404: Message},
    throttle=_limit("announcement_write", "30/m"),
)
def update_announcement(
    request: AuthenticatedHttpRequest, slug: str, payload: AnnouncementUpdateSchema
) -> tuple[int, Announcement | Message]:
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    if not can_manage(request.user, announcement):
        return 403, {"message": "You can't change this announcement."}
    changes = {k: v for k, v in payload.dict(exclude_unset=True).items() if v is not None}
    if problem := _apply(announcement, changes):
        return 400, {"message": problem}
    announcement.save()
    return 200, _with_details(request, announcement)


@router.delete(
    "/{slug}",
    response={204: None, 403: Message, 404: Message},
    throttle=_limit("announcement_write", "30/m"),
)
def delete_announcement(request: AuthenticatedHttpRequest, slug: str) -> tuple[int, Message | None]:
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    if not can_manage(request.user, announcement):
        return 403, {"message": "You can't delete this announcement."}
    announcement.delete()
    return 204, None


@router.post(
    "/{slug}/email",
    response={200: QueuedSchema, 400: Message, 403: Message, 404: Message},
    throttle=_limit("announcement_email", "10/m"),
)
def email_announcement(
    request: AuthenticatedHttpRequest, slug: str, payload: EmailInSchema
) -> tuple[int, QueuedSchema | Message]:
    """Staff email a published announcement to all users, or to members."""
    if not request.user.is_staff:
        return 403, {"message": "Only staff can email everyone."}
    announcement = Announcement.objects.filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    if not announcement.is_published:
        return 400, {"message": "Publish the announcement before emailing it."}
    send = (
        send_announcement_to_all_users
        if payload.audience == "all"
        else send_announcement_to_members
    )
    return 200, QueuedSchema(queued=len(send(announcement)))


@router.post(
    "/{slug}/email/test",
    response={200: QueuedSchema, 400: Message, 403: Message, 404: Message},
    throttle=_limit("announcement_email", "10/m"),
)
def email_announcement_test(
    request: AuthenticatedHttpRequest, slug: str
) -> tuple[int, QueuedSchema | Message]:
    """Whoever manages an announcement can send themselves a copy."""
    announcement = _with_access(request).filter(slug=slug).first()
    if not announcement:
        return 404, {"message": "Announcement not found"}
    if not can_manage(request.user, announcement):
        return 403, {"message": "You can't email this announcement."}
    if not request.user.email:
        return 400, {"message": "Your account has no email address."}
    return 200, QueuedSchema(
        queued=len(send_announcement_to_email(announcement, request.user.email))
    )


@router.get("/{slug}/comments", response={200: list[CommentSchema], 403: Message, 404: Message})
def get_comments(
    request: AuthenticatedHttpRequest, slug: str
) -> list[Comment] | tuple[int, Message]:
    """Top-level comments, oldest first, each with its replies."""
    announcement = _readable(request, slug)
    if isinstance(announcement, tuple):
        return announcement
    authors = ("author", "author__player_profile")
    comments = (
        announcement.comments.filter(parent=None)
        .select_related(*authors)
        .prefetch_related(Prefetch("replies", Comment.objects.select_related(*authors)))
    )
    return _with_comment_reactions(request.user, list(comments))


# ponytail: counts in the default cache, Redis in production (no limit in
# development, whose cache is a dummy). Per user; add a per-post cap if spam gets past it.
@router.post(
    "/{slug}/comments",
    response={201: CommentSchema, 400: Message, 403: Message, 404: Message},
    throttle=_limit("announcement_comment", "10/m"),
)
def create_comment(
    request: AuthenticatedHttpRequest, slug: str, payload: CommentCreateSchema
) -> tuple[int, Comment | Message]:
    announcement = _readable(request, slug)
    if isinstance(announcement, tuple):
        return announcement
    if not announcement.allow_comments:
        return 403, {"message": "Comments are turned off for this announcement."}
    body = payload.body.strip()
    if not body or len(body) > Comment.MAX_LENGTH:
        return 400, {"message": "A comment must be 1 to 2,000 characters."}
    parent_id = None
    if payload.parent_id is not None:
        parent = Comment.objects.filter(
            pk=payload.parent_id, announcement=announcement, is_deleted=False
        ).first()
        if not parent:
            return 400, {"message": "That comment can't be replied to."}
        # A reply to a reply joins the same thread.
        parent_id = parent.parent_id or parent.id
    comment = Comment.objects.create(
        announcement=announcement, author=request.user, parent_id=parent_id, body=body
    )
    return 201, comment


def _readable_comment(
    request: AuthenticatedHttpRequest, comment_id: int
) -> Comment | tuple[int, Message]:
    """The comment, or the 404 or 403 when its announcement can't be read."""
    comment = Comment.objects.select_related("parent").filter(pk=comment_id).first()
    if not comment:
        return 404, {"message": "Comment not found"}
    announcement = _with_access(request).filter(pk=comment.announcement_id).first()
    if not announcement:
        return 404, {"message": "Comment not found"}
    if not _can_read(announcement):
        return 403, {"message": "This announcement is for members only."}
    return comment


def _reactable_comment(
    request: AuthenticatedHttpRequest, comment_id: int
) -> Comment | tuple[int, Message]:
    """A readable comment that isn't deleted: what's gone takes no reactions."""
    comment = _readable_comment(request, comment_id)
    if isinstance(comment, Comment) and comment.is_deleted:
        return 404, {"message": "Comment not found"}
    return comment


@router.delete("/comments/{comment_id}", response={204: None, 403: Message, 404: Message})
def delete_comment(
    request: AuthenticatedHttpRequest, comment_id: int
) -> tuple[int, Message | None]:
    comment = _readable_comment(request, comment_id)
    if isinstance(comment, tuple):
        return comment
    if comment.author_id != request.user.id and not request.user.is_staff:
        return 403, {"message": "You can only delete your own comments."}
    with transaction.atomic():
        # Locked, a reply can't land on a comment between the check and the
        # delete (which would cascade to it).
        list(Comment.objects.select_for_update().filter(pk__in=[comment.pk, comment.parent_id]))
        if comment.replies.exists():
            # Keep the thread: it shows as deleted, with its replies.
            comment.is_deleted, comment.body = True, ""
            comment.save(update_fields=["is_deleted", "body"])
            return 204, None
        comment.delete()
        # Its thread's last reply gone, a deleted comment has nothing left to show.
        parent = comment.parent
        if parent and parent.is_deleted and not parent.replies.exists():
            parent.delete()
    return 204, None


@router.put(
    "/{slug}/reactions/{kind}",
    response={200: list[ReactionCountSchema], 403: Message, 404: Message},
    throttle=_limit("announcement_reaction", "60/m"),
)
def add_reaction(
    request: AuthenticatedHttpRequest, slug: str, kind: Reaction.Kind
) -> list[dict[str, Any]] | tuple[int, Message]:
    announcement = _readable(request, slug)
    if isinstance(announcement, tuple):
        return announcement
    Reaction.objects.get_or_create(announcement=announcement, user=request.user, kind=kind)
    return _reaction_counts(request.user, [announcement.id]).get(announcement.id, [])


@router.delete(
    "/{slug}/reactions/{kind}",
    response={200: list[ReactionCountSchema], 403: Message, 404: Message},
    throttle=_limit("announcement_reaction", "60/m"),
)
def remove_reaction(
    request: AuthenticatedHttpRequest, slug: str, kind: Reaction.Kind
) -> list[dict[str, Any]] | tuple[int, Message]:
    announcement = _readable(request, slug)
    if isinstance(announcement, tuple):
        return announcement
    Reaction.objects.filter(announcement=announcement, user=request.user, kind=kind).delete()
    return _reaction_counts(request.user, [announcement.id]).get(announcement.id, [])


@router.put(
    "/comments/{comment_id}/reactions/{kind}",
    response={200: list[ReactionCountSchema], 403: Message, 404: Message},
    throttle=_limit("comment_reaction", "60/m"),
)
def add_comment_reaction(
    request: AuthenticatedHttpRequest, comment_id: int, kind: Reaction.Kind
) -> list[dict[str, Any]] | tuple[int, Message]:
    comment = _reactable_comment(request, comment_id)
    if isinstance(comment, tuple):
        return comment
    CommentReaction.objects.get_or_create(comment=comment, user=request.user, kind=kind)
    return _comment_reaction_counts(request.user, [comment.id]).get(comment.id, [])


@router.delete(
    "/comments/{comment_id}/reactions/{kind}",
    response={200: list[ReactionCountSchema], 403: Message, 404: Message},
    throttle=_limit("comment_reaction", "60/m"),
)
def remove_comment_reaction(
    request: AuthenticatedHttpRequest, comment_id: int, kind: Reaction.Kind
) -> list[dict[str, Any]] | tuple[int, Message]:
    comment = _reactable_comment(request, comment_id)
    if isinstance(comment, tuple):
        return comment
    CommentReaction.objects.filter(comment=comment, user=request.user, kind=kind).delete()
    return _comment_reaction_counts(request.user, [comment.id]).get(comment.id, [])
