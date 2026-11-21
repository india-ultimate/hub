import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db.models import QuerySet
from django.utils.timezone import now

from server.constants import MAJOR_AGE
from server.core.models import Guardianship, Player, User


def minor_cutoff() -> datetime.date:
    """A player born after this date is a minor."""
    return now().date() - relativedelta(years=MAJOR_AGE)


def wards_of(user: User) -> QuerySet[Guardianship]:
    return Guardianship.objects.filter(user=user, player__date_of_birth__gt=minor_cutoff())


def is_guardian_of(user: Any, player: Player) -> bool:
    return player.is_minor and Guardianship.objects.filter(user=user, player=player).exists()


def may_manage_guardian(user: Any, player: Player) -> bool:
    return player.is_minor and (
        user.pk == player.user_id or user.is_staff or is_guardian_of(user, player)
    )
