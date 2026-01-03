# Generated manually for backfilling Flarum discussions for existing announcements

import logging

from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

logger = logging.getLogger(__name__)


def create_flarum_discussions_for_announcements(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Create Flarum discussions for existing published announcements that don't have forum_discussion_id.
    """
    # Import utility functions and actual User model (needed for methods like get_full_name)
    from server.core.models import User as ActualUser
    from server.flarum.utils import create_flarum_discussion, create_flarum_user

    Announcement = apps.get_model("server", "Announcement")  # noqa: N806

    # Map announcement type to Flarum tag ID
    type_to_tag_id: dict[str, int] = {
        "competitions": 2,  # Competitions
        "executive_board": 3,  # Executive Board
        "finance": 4,  # Finance
        "ntc": 5,  # National Teams
        "governance": 6,  # Governance
        "safeguarding": 7,  # Safeguarding
        "college": 8,  # College
        "development": 9,  # Development
        "operations": 10,  # Operations
        # PROJECT_GAMECHANGERS doesn't have a direct tag, skip it
    }

    # Get base URL
    base_url = getattr(settings, "EMAIL_INVITATION_BASE_URL", "")
    if not base_url:
        logger.warning(
            "EMAIL_INVITATION_BASE_URL not configured, skipping Flarum discussion creation"
        )
        return

    # Get all published announcements that don't have a forum_discussion_id
    announcements = Announcement.objects.select_related("author").filter(
        is_published=True, forum_discussion_id__isnull=True
    )

    created_count = 0
    failed_count = 0

    for announcement in announcements:
        try:
            # Skip if announcement doesn't have a slug
            if not announcement.slug:
                logger.warning(
                    "Skipping announcement '%s' (id: %s) - no slug",
                    announcement.title,
                    announcement.id,
                )
                failed_count += 1
                continue

            # Build announcement URL
            announcement_url = f"{base_url}/announcement/{announcement.slug}"
            content = f"[Read the full announcement here]({announcement_url})"

            # Build tag IDs: always include "Announcements" (id: 1) + type-specific tag
            tag_ids = [1]  # Announcements tag is mandatory
            type_tag_id = type_to_tag_id.get(announcement.type)
            if type_tag_id:
                tag_ids.append(type_tag_id)

            # Ensure author has a Flarum user account
            # Get the actual User instance (not historical) to access methods like get_full_name
            author_id = announcement.author_id
            author = ActualUser.objects.get(pk=author_id)
            user_id = author.forum_id
            if not user_id:
                # Create Flarum user if author doesn't have forum_id
                logger.info(
                    "Author %s (id: %s) does not have forum_id, creating Flarum user",
                    author.username,
                    author.id,
                )
                create_flarum_user(author)
                # Refresh author from database to get the updated forum_id
                author.refresh_from_db()
                user_id = author.forum_id

            # Use forum_id if available, otherwise default to 1
            if not user_id:
                logger.warning(
                    "Could not get forum_id for author %s (id: %s), using default user_id=1",
                    author.username,
                    author.id,
                )
                user_id = 1

            # Create Flarum discussion
            discussion_id = create_flarum_discussion(
                title=announcement.title,
                content=content,
                tag_ids=tag_ids,
                user_id=user_id,
            )

            if discussion_id:
                # Save discussion ID to announcement
                announcement.forum_discussion_id = discussion_id
                announcement.save(update_fields=["forum_discussion_id"])
                created_count += 1
                logger.info(
                    "Created Flarum discussion (id: %s) for announcement '%s' (id: %s)",
                    discussion_id,
                    announcement.title,
                    announcement.id,
                )
            else:
                logger.warning(
                    "Failed to create Flarum discussion for announcement '%s' (id: %s)",
                    announcement.title,
                    announcement.id,
                )
                failed_count += 1
        except Exception:
            logger.exception(
                "Error creating Flarum discussion for announcement '%s' (id: %s)",
                announcement.title,
                announcement.id,
            )
            failed_count += 1

    logger.info(
        "Migration completed: %d discussions created, %d failed",
        created_count,
        failed_count,
    )


def reverse_create_flarum_discussions(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Reverse migration: Clear forum_discussion_id from announcements.
    Note: This does NOT delete the discussions from Flarum.
    """
    Announcement = apps.get_model("server", "Announcement")  # noqa: N806
    Announcement.objects.filter(is_published=True).update(forum_discussion_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0123_announcement_forum_discussion_id"),
    ]

    operations = [
        migrations.RunPython(
            code=create_flarum_discussions_for_announcements,
            reverse_code=reverse_create_flarum_discussions,
        ),
    ]
