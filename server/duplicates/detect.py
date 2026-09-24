"""Finding the accounts that look like one person."""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime

from server.duplicates.identity import (
    name_slug,
    names_agree,
    normalize_email,
    normalize_name,
    normalize_phone,
)

# Rules that put two accounts in one cluster.
RULE_EMAIL = "email"
RULE_NAME_DOB = "name+dob"
RULE_PHONE_DOB = "phone+dob"
RULE_SLUG_DOB = "slug+dob"
RULE_FUZZY_NAME_DOB = "fuzzy-name+dob"

# How each rule reads to the person it is shown to. One table, so the email
# and the page can never describe the same cluster differently.
RULE_WORDING = {
    RULE_EMAIL: "an email address",
    RULE_NAME_DOB: "a name and date of birth",
    RULE_PHONE_DOB: "a phone number and date of birth",
    RULE_SLUG_DOB: "a name and date of birth",
    RULE_FUZZY_NAME_DOB: "a very similar name and the same date of birth",
}


def matched_on(matched_by: str) -> str:
    """Plain wording for what put a group together."""
    wording = [RULE_WORDING[rule] for rule in matched_by.split() if rule in RULE_WORDING]
    return wording[0] if wording else "some of the same details"


# Reasons a cluster must never be offered for merging.
BLOCK_GUARDIANSHIP = "guardianship"
BLOCK_DIFFERENT_WARDS = "different-wards"
BLOCK_NAME_MISMATCH = "name-mismatch"
BLOCK_DIFFERENT_GUARDIANS = "different-guardians"
BLOCK_DIFFERENT_GENDER = "different-gender"

MIN_CLUSTER_SIZE = 2
MIN_NAME_COUNT = 1


@dataclass(frozen=True)
class Candidate:
    user_id: int
    player_id: int
    email: str
    username: str
    phone: str
    first_name: str
    last_name: str
    date_of_birth: date
    ultimate_central_id: int | None
    last_login: datetime | None
    gender: str = ""

    @property
    def name(self) -> tuple[str, str]:
        return (self.first_name, self.last_name)

    @property
    def has_deliverable_email(self) -> bool:
        return "@" in self.email


@dataclass
class Cluster:
    members: list[Candidate]
    rules: set[str]
    blockers: list[str]

    @property
    def is_mergeable(self) -> bool:
        return not self.blockers


class _Union:
    """Union-find, so accounts linked by different rules land in one cluster."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, item: int) -> int:
        self._parent.setdefault(item, item)
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_b] = root_a


def load_candidates() -> list[Candidate]:
    from server.core.models import Player

    return [
        Candidate(
            user_id=player.user_id,
            player_id=player.id,
            email=player.user.email,
            username=player.user.username,
            phone=player.user.phone,
            first_name=player.user.first_name,
            last_name=player.user.last_name,
            date_of_birth=player.date_of_birth,
            ultimate_central_id=player.ultimate_central_id,
            last_login=player.user.last_login,
            gender=player.gender,
        )
        for player in Player.objects.select_related("user").order_by("user_id")
    ]


def _exact_keys(candidate: Candidate) -> Iterator[tuple[str, str]]:
    dob = candidate.date_of_birth.isoformat()

    email = normalize_email(candidate.email)
    if "@" in email:
        yield RULE_EMAIL, email

    name = normalize_name(candidate.first_name, candidate.last_name)
    if name:
        yield RULE_NAME_DOB, f"{name}|{dob}"

    phone = normalize_phone(candidate.phone)
    if phone:
        yield RULE_PHONE_DOB, f"{phone}|{dob}"

    # An account registered without an email has the slug as its username;
    # the account the same person creates later only has the name.
    slugs = {name_slug(candidate.first_name, candidate.last_name), candidate.username.casefold()}
    for slug in slugs:
        if slug and "@" not in slug:
            yield RULE_SLUG_DOB, f"{slug}|{dob}"


def _link_exact(candidates: list[Candidate], union: _Union, rules: dict[int, set[str]]) -> None:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for candidate in candidates:
        for rule, key in _exact_keys(candidate):
            grouped[(rule, key)].append(candidate.user_id)

    for (rule, _), user_ids in grouped.items():
        if len(user_ids) < MIN_CLUSTER_SIZE:
            continue
        for user_id in user_ids:
            rules[user_id].add(rule)
            union.union(user_ids[0], user_id)


def _link_fuzzy(candidates: list[Candidate], union: _Union, rules: dict[int, set[str]]) -> None:
    """Compare names only within a date of birth, which keeps this quadratic
    in the size of a birthday rather than in the size of the table."""
    by_dob: dict[date, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_dob[candidate.date_of_birth].append(candidate)

    for same_dob in by_dob.values():
        if len(same_dob) < MIN_CLUSTER_SIZE:
            continue
        names = [(c, normalize_name(c.first_name, c.last_name)) for c in same_dob]
        for index, (left, left_name) in enumerate(names):
            for right, right_name in names[index + 1 :]:
                if not left_name or not right_name or left_name == right_name:
                    continue  # an exact match is already the name+dob rule
                if names_agree(left.name, right.name) and _share_contact(left, right):
                    rules[left.user_id].add(RULE_FUZZY_NAME_DOB)
                    rules[right.user_id].add(RULE_FUZZY_NAME_DOB)
                    union.union(left.user_id, right.user_id)


def _share_contact(left: Candidate, right: Candidate) -> bool:
    """A second signal for a name that is only close: the same phone, or the
    same mailbox name at any provider. A near name and a birthday alone was
    half of the surname typos in production, with nothing else in common.

    The +tag stays in the mailbox name, so an NGO worker's children, who
    share everything but the tag, do not count as sharing an address.
    """
    phone = normalize_phone(left.phone)
    if phone and phone == normalize_phone(right.phone):
        return True
    mailbox, sep, _ = normalize_email(left.email).rpartition("@")
    return bool(sep and mailbox) and mailbox == normalize_email(right.email).rpartition("@")[0]


def different_wards(player_ids: list[int], names: set[str]) -> bool:
    """Whether these are two dependents of one guardian rather than one person.

    The guardian is not a cluster member, so the edge below never sees a pair
    of siblings. They reach a cluster through the parent's phone, which needs
    a shared birthday too, so in practice this is twins. The name is what
    separates them from one child registered twice, which should still merge.
    """
    from server.core.models import Guardianship

    if len(names) < MIN_CLUSTER_SIZE:
        return False
    return Guardianship.objects.filter(player_id__in=player_ids).count() >= MIN_CLUSTER_SIZE


def different_guardians(player_ids: list[int]) -> bool:
    """Whether one child is claimed by two different guardians.

    A child registered twice by the same parent is a duplicate and merges;
    the spare guardianship row goes and nothing is lost. Registered once by
    each parent it is still one child, but only one of those rows can
    survive the one-to-one, and picking a parent is not ours to do.
    """
    from server.core.models import Guardianship

    guardians = set(
        Guardianship.objects.filter(player_id__in=player_ids).values_list("user_id", flat=True)
    )
    return len(guardians) > MIN_NAME_COUNT


def different_gender(genders: list[str]) -> bool:
    """Two accounts with one name and one birthday but different recorded
    genders. Only two such groups exist in production; refusing them is the
    cheap way to be wrong."""
    return len({gender for gender in genders if gender}) > 1


def name_mismatch(names: list[tuple[str, str]]) -> bool:
    """Whether the group holds two people who are named differently.

    An address or a phone number is shared on purpose: a family inbox, a
    coach's number, an NGO worker holding the accounts of the children they
    look after. None of that makes two people one person.

    Two accounts the name rules agree on share a name by construction, so a
    disagreement means at least one member was pulled in by something else -
    directly, or through a chain of other members. Reading the cluster's
    rules instead would miss that: one matching pair anywhere is enough to
    make the whole cluster look name-matched.

    Names are compared the way the fuzzy rule compares them, so a spelling
    that was close enough to group these accounts is close enough to keep
    them grouped.

    One account with no name at all is not a disagreement. That is the empty
    account signing in creates, which is what this flow exists to clear up.
    Two of them is: nothing says they are one person, and twins who each
    signed in by OTP on a family phone look exactly like that.
    """
    named = [name for name in names if normalize_name(*name)]
    if len(names) - len(named) > 1:
        return True
    return any(
        not names_agree(left, right)
        for index, left in enumerate(named)
        for right in named[index + 1 :]
    )


def find_blockers(members: list[Candidate]) -> list[str]:
    from django.db.models import F

    from server.core.models import Guardianship

    blockers = []

    # A parent and child share an inbox and a phone legitimately. An account
    # listed as its own player's guardian is not that, and must not block.
    if (
        Guardianship.objects.filter(
            user_id__in=[m.user_id for m in members],
            player_id__in=[m.player_id for m in members],
        )
        .exclude(user=F("player__user"))
        .exists()
    ):
        blockers.append(BLOCK_GUARDIANSHIP)

    names = {normalize_name(m.first_name, m.last_name) for m in members}
    if different_wards([m.player_id for m in members], names):
        blockers.append(BLOCK_DIFFERENT_WARDS)

    if name_mismatch([m.name for m in members]):
        blockers.append(BLOCK_NAME_MISMATCH)

    if different_guardians([m.player_id for m in members]):
        blockers.append(BLOCK_DIFFERENT_GUARDIANS)

    if different_gender([m.gender for m in members]):
        blockers.append(BLOCK_DIFFERENT_GENDER)

    return blockers


def find_clusters() -> list[Cluster]:
    """Group accounts believed to be one person, most accounts first."""
    candidates = load_candidates()
    union = _Union()
    rules: dict[int, set[str]] = defaultdict(set)

    _link_exact(candidates, union, rules)
    _link_fuzzy(candidates, union, rules)

    grouped: dict[int, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        if rules[candidate.user_id]:
            grouped[union.find(candidate.user_id)].append(candidate)

    clusters = [
        Cluster(
            members=sorted(members, key=_most_used_first),
            rules={rule for m in members for rule in rules[m.user_id]},
            blockers=find_blockers(members),
        )
        for members in grouped.values()
        if len(members) >= MIN_CLUSTER_SIZE
    ]
    return sorted(clusters, key=lambda c: (-len(c.members), c.members[0].user_id))


def _most_used_first(candidate: Candidate) -> tuple[bool, float, int]:
    """The account the person actually uses, then oldest, for a stable order."""
    last_login = candidate.last_login
    return (last_login is None, -last_login.timestamp() if last_login else 0.0, candidate.user_id)
