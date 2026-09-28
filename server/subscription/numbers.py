"""The IU-YY-NNNN a person keeps for life."""

import re

from django.db import IntegrityError, transaction

from server.core.models import Player
from server.season.models import Season

PREFIX = "IU"
PATTERN = re.compile(r"^IU-(\d{2})-(\d+)$")
RETRIES = 5


def season_code(season: Season) -> str:
    """The two-digit year a season starts in."""
    return f"{season.start_date.year % 100:02d}"


def format_number(season: Season, position: int) -> str:
    return f"{PREFIX}-{season_code(season)}-{position:04d}"


def next_position(season: Season) -> int:
    """One past the highest number already issued for this season's year."""
    code = season_code(season)
    highest = 0
    numbers = Player.objects.filter(iu_id__startswith=f"{PREFIX}-{code}-").values_list(
        "iu_id", flat=True
    )
    for number in numbers:
        match = PATTERN.match(number or "")
        if match and match.group(1) == code:
            highest = max(highest, int(match.group(2)))
    return highest + 1


def assign_number(player: Player, season: Season) -> str:
    """Give a player their number, if they do not have one already.

    The number names the season someone first held a subscription, and never
    changes afterwards. Two people registering at once can pick the same
    position, so a clash on the unique column simply tries the next one.
    """
    if player.iu_id:
        return player.iu_id

    for _ in range(RETRIES):
        candidate = format_number(season, next_position(season))
        try:
            with transaction.atomic():
                player.iu_id = candidate
                player.save(update_fields=["iu_id"])
            return candidate
        except IntegrityError:
            player.iu_id = None
    raise IntegrityError(f"Could not allocate an IU ID for player {player.pk}")
