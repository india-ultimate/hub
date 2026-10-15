from collections.abc import Iterable
from typing import Any

from django.db import transaction
from django.db.models import BooleanField, Case, Count, Prefetch, Q, QuerySet, Value, When
from django.http import HttpRequest
from ninja import Router
from ninja.throttling import AuthRateThrottle

from server.announcements.access import can_read_members_only
from server.announcements.models import Announcement, Comment, CommentReaction, Reaction
from server.announcements.schema import (
    AnnouncementSchema,
    CommentCreateSchema,
    CommentSchema,
    ReactionCountSchema,
    _can_read,
)
from server.core.models import User

# Create announcements router
router = Router()

Message = dict[str, str]
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
    if not request.user.is_staff:
        # Public users see only published announcements
        qs = qs.filter(is_published=True)
    return qs.annotate(
        can_read=Case(
            When(is_members_only=False, then=Value(True)),
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
