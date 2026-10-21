from django.db import models
from django.db.models import Q

from server.core.models import User
from server.ticket.models import TicketCategory
from server.utils import today


class Committee(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # "manage" is refused by the API: it is the staff page's path
    slug = models.SlugField(unique=True)
    # The committee's shared address, the only one the public page shows
    email = models.EmailField(blank=True)
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    # Everyone with a current role here may post announcements
    can_post_announcements = models.BooleanField(default=False, db_default=False)
    # Everyone with a current role here may create forms
    can_create_forms = models.BooleanField(default=False, db_default=False)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class RoleQuerySet(models.QuerySet["Role"]):
    def current(self) -> "RoleQuerySet":
        """The roles held today. end_date is the first day a role no longer holds."""
        return self.filter(start_date__lte=today()).filter(
            Q(end_date__isnull=True) | Q(end_date__gt=today())
        )

    def past(self) -> "RoleQuerySet":
        return self.filter(end_date__lte=today())


class Role(models.Model):
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name="roles")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="committee_roles")
    title = models.CharField(max_length=60)
    # Chairs are assigned each new ticket the committee handles
    is_chair = models.BooleanField(default=False)
    # This person may post announcements, whatever their committee allows
    can_post_announcements = models.BooleanField(default=False, db_default=False)
    # This person may create forms, whatever their committee allows
    can_create_forms = models.BooleanField(default=False, db_default=False)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    objects = RoleQuerySet.as_manager()

    def __str__(self) -> str:
        return f"{self.user} - {self.title}, {self.committee}"


class TicketRoute(models.Model):
    """A category of ticket that a committee handles. A category with no route
    stays unassigned for Ops."""

    category = models.ForeignKey(
        TicketCategory,
        to_field="key",
        db_column="category",
        on_delete=models.PROTECT,
        related_name="routes",
    )
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name="routes")

    class Meta:
        unique_together = ("category", "committee")

    def __str__(self) -> str:
        return f"{self.category_id} -> {self.committee}"
