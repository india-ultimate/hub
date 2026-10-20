from django.db import models
from django.utils.text import slugify

from server.core.models import User


class TicketCategory(models.Model):
    """What a ticket is about. Staff manage these; they are retired, never deleted."""

    NAME_MAX_LENGTH = 100

    # Set once and never changed: it is what tickets and routes store
    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=NAME_MAX_LENGTH, unique=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_retired = models.BooleanField(default=False, db_default=False)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def new_key(cls, name: str) -> str:
        """The slug of `name`, with -2, -3 and so on added if taken."""
        base = slugify(name)[:90] or "category"
        key, n = base, 1
        while cls.objects.filter(key=key).exists():
            n += 1
            key = f"{base}-{n}"
        return key


class Ticket(models.Model):
    # Explicitly define id for type checking
    id = models.AutoField(primary_key=True)

    class Status(models.TextChoices):
        OPEN = "OPN", "Open"
        IN_PROGRESS = "PRG", "In Progress"
        RESOLVED = "RES", "Resolved"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MED", "Medium"
        HIGH = "HIG", "High"
        URGENT = "URG", "Urgent"

    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tickets")
    # Kept only so the release still running during a deploy can read this
    # column. Nothing reads or writes it any more: see `assignees`. Field and
    # column are removed together in the follow-up branch.
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_assigned_tickets",
    )
    assignees = models.ManyToManyField(User, blank=True, related_name="assigned_tickets")
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=3, choices=Priority.choices, default=Priority.MEDIUM)
    category = models.ForeignKey(
        "TicketCategory",
        to_field="key",
        db_column="category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )
    # Seen only by its creator and staff, for things not meant for everyone.
    is_private = models.BooleanField(default=False)
    # People saying this matters to them too, so staff can see what to fix first.
    upvoters = models.ManyToManyField(User, blank=True, related_name="upvoted_tickets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Its title or description's last change; updated_at moves with the status too.
    edited_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.id} - {self.title}"


class TicketMessage(models.Model):
    # Explicitly define id for type checking
    id = models.AutoField(primary_key=True)

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    attachment = models.URLField(max_length=512, null=True, blank=True)

    def __str__(self) -> str:
        return f"Message on ticket {self.ticket.id} by {self.sender.username}"
