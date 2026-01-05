import logging
from typing import Any

from ckeditor_uploader.fields import RichTextUploadingField
from django.db import models
from django.utils.text import slugify
from markdownify import markdownify as md

from server.core.models import User
from server.flarum.utils import create_flarum_discussion, create_flarum_user

logger = logging.getLogger(__name__)


class Announcement(models.Model):
    class Type(models.TextChoices):
        COMPETITIONS = "competitions", "Competitions"
        EXECUTIVE_BOARD = "executive_board", "Executive Board"
        PROJECT_GAMECHANGERS = "project_gamechangers", "Project GameChangers"
        FINANCE = "finance", "Finance"
        NTC = "ntc", "NTC"
        GOVERNANCE = "governance", "Governance"
        SAFEGUARDING = "safeguarding", "Safeguarding"
        COLLEGE = "college", "College"
        DEVELOPMENT = "development", "Development"
        OPERATIONS = "operations", "Operations"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = RichTextUploadingField()
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.COMPETITIONS)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_members_only = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    # Optional CTA fields
    action_text = models.CharField(max_length=100, blank=True, null=True)
    action_url = models.URLField(blank=True, null=True)

    # Flarum discussion ID
    forum_discussion_id = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Check if this is being published for the first time
        was_published = False
        if self.pk:
            try:
                old_instance = Announcement.objects.get(pk=self.pk)
                was_published = old_instance.is_published
            except Announcement.DoesNotExist:
                was_published = False

        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Announcement.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        super().save(*args, **kwargs)

        # Create Flarum discussion when announcement is published
        if self.is_published and not was_published:
            self._create_flarum_discussion()

    def _get_flarum_tag_id_for_type(self) -> int | None:
        """Map announcement type to Flarum tag ID."""
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
        return type_to_tag_id.get(self.type)

    def _create_flarum_discussion(self) -> None:
        """Create a Flarum discussion for this announcement."""
        try:
            # Convert HTML content to Markdown
            content = md(self.content, heading_style="ATX")

            # Build tag IDs: always include "Announcements" (id: 1) + type-specific tag + Members Only if applicable
            tag_ids = [1]  # Announcements tag is mandatory
            type_tag_id = self._get_flarum_tag_id_for_type()
            if type_tag_id:
                tag_ids.append(type_tag_id)

            # Add "Members Only" tag (id: 19) if announcement is members only
            if self.is_members_only:
                tag_ids.append(19)

            # Ensure author has a Flarum user account
            user_id = self.author.forum_id
            if not user_id:
                # Create Flarum user if author doesn't have forum_id
                logger.info(
                    "Author %s does not have forum_id, creating Flarum user", self.author.username
                )
                create_flarum_user(self.author)
                # Refresh author from database to get the updated forum_id
                self.author.refresh_from_db()
                user_id = self.author.forum_id

            # Use forum_id if available, otherwise default to 1
            if not user_id:
                logger.warning(
                    "Could not get forum_id for author %s, using default user_id=1",
                    self.author.username,
                )
                user_id = 1

            # Create Flarum discussion
            discussion_id = create_flarum_discussion(
                title=self.title,
                content=content,
                tag_ids=tag_ids,
                user_id=user_id,
                created_at=self.created_at,
            )

            if discussion_id:
                # Save discussion ID to announcement
                self.forum_discussion_id = discussion_id
                Announcement.objects.filter(pk=self.pk).update(forum_discussion_id=discussion_id)
                logger.info(
                    "Created Flarum discussion (id: %s) for announcement: %s",
                    discussion_id,
                    self.title,
                )
            else:
                logger.warning(
                    "Failed to create Flarum discussion for announcement: %s", self.title
                )
        except Exception:
            logger.exception("Error creating Flarum discussion for announcement %s", self.title)
