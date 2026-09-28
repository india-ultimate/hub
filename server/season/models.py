import datetime
import logging

from django.db import models
from django_prometheus.models import ExportModelOperationsMixin

from server.utils import today

logger = logging.getLogger(__name__)


class Season(ExportModelOperationsMixin("season"), models.Model):  # type: ignore[misc]
    start_date = models.DateField()
    end_date = models.DateField()
    name = models.CharField(max_length=255)
    annual_subscription_amount = models.PositiveIntegerField(default=0)
    sponsored_annual_subscription_amount = models.PositiveIntegerField(default=0)
    supporter_annual_subscription_amount = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return self.name

    @classmethod
    def current(cls) -> "Season | None":
        """The season today falls inside, in IST."""
        season = cls.containing(today())
        if season is None:
            logger.warning("No season covers today (%s)", today())
        return season

    @classmethod
    def containing(cls, day: datetime.date) -> "Season | None":
        """The season a given date falls inside.

        Production seasons don't overlap, but test fixtures create ones that
        do, so the tie-break is defined rather than left to whatever order
        the database happens to return rows in: the season that started
        most recently wins, and a tie on start_date goes to whichever was
        created most recently.
        """
        return (
            cls.objects.filter(start_date__lte=day, end_date__gte=day)
            .order_by("-start_date", "-id")
            .first()
        )
