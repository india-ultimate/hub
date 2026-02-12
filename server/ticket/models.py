from django.db import models

from server.core.models import User


class Ticket(models.Model):
    # Explicitly define id for type checking
    id = models.AutoField(primary_key=True)

    class Status(models.TextChoices):
        OPEN = "OPN", "Open"
        IN_PROGRESS = "PRG", "In Progress"
        RESOLVED = "RES", "Resolved"
        CLOSED = "CLS", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MED", "Medium"
        HIGH = "HIG", "High"
        URGENT = "URG", "Urgent"

    class Category(models.TextChoices):
        ACCOUNT = "Account", "Account"
        COMPETITIONS = "Competitions", "Competitions"
        MEMBERSHIP = "Membership", "Membership"
        TOURNAMENT = "Tournament", "Tournament"
        PAYMENT = "Payment", "Payment"
        TECH = "Tech", "Tech"
        OTHER = "Other", "Other"

    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tickets")
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets"
    )
    status = models.CharField(max_length=3, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=3, choices=Priority.choices, default=Priority.MEDIUM)
    category = models.CharField(
        max_length=100, choices=Category.choices, blank=True, null=True, default=Category.OTHER
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.id} - {self.title}"

    # For type checking with mypy
    def get_priority_display(self) -> str:
        """Get the human-readable priority value."""
        for code, value in self.Priority.choices:
            if code == self.priority:
                return value
        return ""

    def get_status_display(self) -> str:
        """Get the human-readable status value."""
        for code, value in self.Status.choices:
            if code == self.status:
                return value
        return ""

    def get_category_display(self) -> str:
        """Get the human-readable category value."""
        for code, value in self.Category.choices:
            if code == self.category:
                return value
        return ""


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
