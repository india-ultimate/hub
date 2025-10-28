from typing import Any

from ckeditor_uploader.fields import RichTextUploadingField
from django.db import models
from django.utils.text import slugify

from server.core.models import User


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

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Announcement.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
