"""Two accounts side by side, for whoever decides on a merge."""

from collections.abc import Callable
from dataclasses import dataclass

from server.core.models import Player, User
from server.duplicates.detect import (
    BLOCK_DIFFERENT_GENDER,
    BLOCK_DIFFERENT_GUARDIANS,
    BLOCK_DIFFERENT_WARDS,
    BLOCK_GUARDIANSHIP,
    BLOCK_NAME_MISMATCH,
)
from server.duplicates.identity import normalize_name

IDENTITY = frozenset(
    {"Name", "Date of birth", "Gender", "City", "Has a player profile", "Ultimate Central id"}
)

BLOCKER_WORDING = {
    BLOCK_GUARDIANSHIP: "One account is the other's parent or guardian",
    BLOCK_DIFFERENT_WARDS: "They look like two children of the same guardian",
    BLOCK_DIFFERENT_GUARDIANS: "They have different guardians",
    BLOCK_NAME_MISMATCH: "The names do not match",
    BLOCK_DIFFERENT_GENDER: "The recorded gender is different",
}


def in_words(blockers: list[str]) -> list[str]:
    return [BLOCKER_WORDING.get(blocker, blocker) for blocker in blockers]


@dataclass(frozen=True)
class Line:
    label: str
    values: list[str]

    @property
    def differs(self) -> bool:
        """Only identity rows, and a blank is unknown rather than different."""
        if self.label not in IDENTITY:
            return False
        if self.label == "Has a player profile":
            return len(set(self.values)) > 1
        values = {value for value in self.values if value}
        if self.label == "Name":
            values = {normalize_name(value, "") for value in values}
        return len(values) > 1


def _membership(player: Player) -> str:
    membership = getattr(player, "membership", None)
    if membership is None:
        return ""
    return f"{membership.start_date}..{membership.end_date}" if membership.is_active else "expired"


def compare(keeper: User, others: list[User]) -> list[Line]:
    accounts = [keeper, *others]

    def profile(label: str, value: Callable[[Player], object]) -> Line:
        values = [value(p) if (p := getattr(u, "player_profile", None)) else None for u in accounts]
        return Line(label, ["" if v is None else str(v) for v in values])

    return [
        Line("Name", [user.get_full_name() for user in accounts]),
        profile("Date of birth", lambda p: p.date_of_birth),
        profile("Gender", lambda p: p.get_gender_display()),
        profile("City", lambda p: p.city),
        Line("Signs in with", [user.username for user in accounts]),
        Line("Email", [user.email for user in accounts]),
        Line("Phone", [user.phone or "" for user in accounts]),
        Line("Last login", [str(user.last_login or "never") for user in accounts]),
        profile("Has a player profile", lambda p: "yes"),
        profile("Membership", _membership),
        profile("Teams", lambda p: ", ".join(team.name for team in p.teams.all())),
        profile("Tournament registrations", lambda p: p.registration_set.count()),
        profile("Ultimate Central id", lambda p: p.ultimate_central_id),
    ]
