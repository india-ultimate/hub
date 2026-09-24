"""Merging one account into another without losing a row.

Relations are walked at runtime rather than listed, because a list goes stale
and a model missing from it is not skipped, it is cascade-deleted. The walk is
then checked: nothing may still point at an absorbed account when it is
deleted, so forgetting a table fails the transaction instead of losing data.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.db import IntegrityError, transaction
from django.db.models import F, Model, Q
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.fields.reverse_related import ManyToManyRel

from server.core.models import Guardianship, Player, User
from server.duplicates.clusters import close_emptied
from server.duplicates.detect import (
    BLOCK_DIFFERENT_GENDER,
    BLOCK_DIFFERENT_GUARDIANS,
    BLOCK_DIFFERENT_WARDS,
    BLOCK_GUARDIANSHIP,
    BLOCK_NAME_MISMATCH,
    different_gender,
    different_guardians,
    different_wards,
    name_mismatch,
)
from server.duplicates.history import log
from server.duplicates.identity import normalize_name
from server.duplicates.models import (
    AccountMerge,
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
)
from server.duplicates.staff import close_request

# Which row survives when both accounts hold one the merge cannot duplicate,
# whether that is a one-to-one or a unique_together. Higher sorts better; the
# loser is kept in the audit snapshot. A model with no entry here keeps the
# primary's row, which is only safe where the two rows are interchangeable.
# The answers a person wrote about themselves. Nothing here is rankable on its
# own, so the row with more of them filled in is the one worth keeping.
COMMENTARY_FIELDS = (
    "jersey_number",
    "ultimate_origin",
    "ultimate_attraction",
    "ultimate_fav_role",
    "ultimate_fav_exp",
    "interests",
    "fun_fact",
)

ROW_PREFERENCE = {
    "server.Membership": lambda row: (row.is_active, row.end_date),
    "server.Accreditation": lambda row: (row.is_valid, row.date),
    "server.Vaccination": lambda row: (row.is_vaccinated,),
    "server.CollegeId": lambda row: (row.expiry,),
    # A used verification records that this person has already voted. Losing
    # it to an unused one would let the merged account vote a second time.
    "server.VoterVerification": lambda row: (row.is_used,),
    "server.Registration": lambda row: (row.is_playing, row.points or 0),
    "server.PlayerWrapped": lambda row: (row.total_games or 0,),
    "server.CommentaryInfo": lambda row: (
        sum(1 for name in COMMENTARY_FIELDS if getattr(row, name, None)),
    ),
    # server.Player.user has no entry: merge_accounts's dedicated Player
    # phase always deletes or reassigns a duplicate's Player row before the
    # generic relation walk reaches this one, so there is never a second
    # row left to clash with primary's. Unreachable, not forgotten.
}

# The one-to-ones resolved up front, before the relation walk.
O2O_PREFERENCE = {
    label: rank
    for label, rank in ROW_PREFERENCE.items()
    if label
    in {"server.Membership", "server.Accreditation", "server.Vaccination", "server.CollegeId"}
}

# Filled from the duplicate when the primary has nothing there. email is absent
# on purpose: username is the address sign in resolves on, and writing one
# without the other would strand the account. The address becomes an EmailAlias.
USER_FILLABLE = ("first_name", "last_name", "phone")
PLAYER_FILLABLE = (
    # Filling a blank is an OR for a flag: the survivor keeps sponsorship if
    # either account had it. A merge must never take away something granted.
    "sponsored",
    "city",
    "state_ut",
    "occupation",
    "educational_institution",
    "ultimate_central_id",
    "profile_pic_url",
    "other_gender",
)


# Never worth keeping once the account is gone, and the snapshot outlives it.
SNAPSHOT_REDACTED = ("password",)


def _snapshot(rows: list[Model]) -> list[dict[str, Any]]:
    """Serialize the rows a merge destroys, minus anything that is a secret."""
    serialized = json.loads(serialize("json", rows))
    for row in serialized:
        if row["model"] == "server.user":
            for name in SNAPSHOT_REDACTED:
                row["fields"].pop(name, None)
    return serialized


def _jsonable(value: Any) -> Any:
    """Field values go into a JSONField, so dates and the like become text."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


@dataclass
class MergeRecord:
    """What the merge actually did, row by row.

    A count cannot be undone. Once a row points at the surviving account
    nothing in the database says where it came from, and that fact exists
    only while the merge is running - so it is written down as it happens.

    This records; it does not reverse. It is what a reversal would be built
    from, alongside the snapshot of the rows that were deleted.
    """

    moves: list[dict[str, Any]] = field(default_factory=list)
    overwrites: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[dict[str, Any]] = field(default_factory=list)
    aliases: list[dict[str, Any]] = field(default_factory=list)
    proof: dict[str, Any] = field(default_factory=dict)

    def moved(self, label: str, pk: Any, name: str, was: Any, now: Any) -> None:
        # Every value goes through _jsonable: a pk is usually an int, but
        # PhonePeTransaction is keyed by a UUID, and one of those reaching
        # the JSONField raw aborts the whole merge.
        self.moves.append(
            {
                "model": label,
                "pk": _jsonable(pk),
                "field": name,
                "was": _jsonable(was),
                "now": _jsonable(now),
            }
        )

    def linked(
        self, label: str, name: str, other_pk: Any, was: Any, now: Any, already_held: bool
    ) -> None:
        """One many-to-many entry moved across.

        other_pk is the end that stayed put. already_held says the target was
        already in that set, so the move was really a removal from the source
        - undoing it by unlinking the target would take away a link that was
        there before the merge.
        """
        self.moves.append(
            {
                "model": label,
                "field": name,
                "other_pk": _jsonable(other_pk),
                "was": _jsonable(was),
                "now": _jsonable(now),
                "already_held": already_held,
            }
        )

    def overwrote(self, target: Model, name: str, was: Any, now: Any) -> None:
        self.overwrites.append(
            {
                "model": target._meta.label,
                "pk": _jsonable(target.pk),
                "field": name,
                "was": _jsonable(was),
                "now": _jsonable(now),
            }
        )

    def destroyed(self, row: Model, reason: str) -> None:
        """A row this merge deleted. Its contents are in the snapshot; this
        says which row that was and why it went, which the snapshot cannot."""
        self.deleted.append({"model": row._meta.label, "pk": _jsonable(row.pk), "reason": reason})

    def aliased(self, email: str, user_id: int, replaced_user_id: int | None) -> None:
        """An absorbed address, and whose alias it was before, if anyone's."""
        self.aliases.append(
            {"email": email, "user_id": user_id, "replaced_user_id": replaced_user_id}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "moves": self.moves,
            "overwrites": self.overwrites,
            "deleted": self.deleted,
            "aliases": self.aliases,
            "proof": self.proof,
        }


class MergeBlockedError(Exception):
    """The accounts must not be merged."""


class MergeIncompleteError(Exception):
    """Rows still point at an account about to be deleted."""


class MergeFieldError(Exception):
    """A value the person picked on the review step cannot be stored."""


# Second line only: PlayerFormSchema already refuses these as input, because
# they are administrative. Kept so that widening the form cannot quietly put a
# fee discount on the review page.
NOT_RESOLVABLE = frozenset({"imported_data", "sponsored"})


def resolvable_fields() -> tuple[frozenset[str], frozenset[str]]:
    """The fields the review step may set, taken from the registration form so
    the two cannot drift apart.

    email is absent by construction: username is the address and sign in
    resolves on it, so an edit here would lock the person out.
    """
    from server.schema import PlayerFormSchema, UserFormSchema

    return (
        frozenset(UserFormSchema.__fields__),
        frozenset(PlayerFormSchema.__fields__) - NOT_RESOLVABLE,
    )


def _apply_resolved(
    primary: User,
    primary_player: Player | None,
    duplicates: list[User],
    duplicate_players: list[Player],
    resolved: dict[str, Any],
    record: MergeRecord | None = None,
) -> None:
    """Write the values the person chose over what the merge worked out."""
    user_fields, player_fields = resolvable_fields()

    unknown = set(resolved) - user_fields - player_fields
    if unknown:
        raise MergeFieldError(f"Not something you can set here: {', '.join(sorted(unknown))}")

    # A blank answer means "no preference", and the page leaves those out. One
    # arriving anyway would erase a detail the merge just recovered from the
    # other account, and full_clean only catches that on required fields. Say
    # so rather than writing it: loud beats lossy on something irreversible.
    blank = sorted(name for name, value in resolved.items() if value is None or value == "")
    if blank:
        raise MergeFieldError(f"Leave a detail out rather than blanking it: {', '.join(blank)}")
    if primary_player is None and set(resolved) & player_fields:
        raise MergeFieldError("These accounts have no profile to put those details on")

    # A choice is always one of the two accounts' own values - the radio
    # buttons never offer anything else, and a raw API call must not be
    # able to smuggle a third value past them. This does not close off
    # setting an arbitrary value generally: the person can still edit
    # their own profile afterwards through the normal form: a different,
    # already-open door to the same fields.
    users = [primary, *duplicates]
    players = [player for player in [primary_player, *duplicate_players] if player is not None]
    for name, value in resolved.items():
        holders: list[Model] = list(users) if name in user_fields else list(players)
        known = {
            str(getattr(holder, name)) for holder in holders if getattr(holder, name) is not None
        }
        if str(value) not in known:
            raise MergeFieldError(f"Not one of these accounts' own values: {name}")

    for target, allowed in ((primary, user_fields), (primary_player, player_fields)):
        if target is None:
            continue
        touched = sorted(set(resolved) & allowed)
        if not touched:
            continue
        for name in touched:
            if record is not None:
                record.overwrote(target, name, getattr(target, name, None), resolved[name])
            setattr(target, name, resolved[name])
        # Only the fields being set: an account may already hold something
        # the form would reject, and that must not block the merge.
        untouched = [f.name for f in target._meta.fields if f.name not in touched]
        try:
            target.full_clean(exclude=untouched)
        except ValidationError as invalid:
            raise MergeFieldError("; ".join(invalid.messages)) from invalid
        target.save(update_fields=touched)


@dataclass
class RelationMove:
    label: str
    moved: int = 0
    collided: int = 0
    # Of the clashes, the ones where the primary's own row is the weaker and
    # gets dropped. Worth calling out: it is the surprising direction.
    primary_loses: int = 0


@dataclass
class MergePlan:
    primary_user_id: int
    duplicate_user_ids: list[int]
    moves: list[RelationMove] = field(default_factory=list)
    merge_id: int | None = None

    @property
    def rows_moved(self) -> int:
        return sum(move.moved for move in self.moves)

    def record(self, label: str, moved: int, collided: int, primary_loses: int = 0) -> None:
        if moved or collided:
            self.moves.append(RelationMove(label, moved, collided, primary_loses))

    def as_dict(self) -> dict[str, Any]:
        return {
            "primary_user_id": self.primary_user_id,
            "duplicate_user_ids": self.duplicate_user_ids,
            "moves": [
                {
                    "relation": m.label,
                    "moved": m.moved,
                    "collided": m.collided,
                    "primary_loses": m.primary_loses,
                }
                for m in self.moves
            ],
        }


# History, not ownership. A group row says who was in the group; moving it to
# the keeper, or deleting it on a clash, would erase that. _settle_group_rows
# handles these explicitly instead, and the dangling-reference guard skips
# them because it walks the same list.
NOT_WALKED = frozenset({"server.ClusterMember.user"})


def inbound_relations(model: type[Model]) -> list[ForeignObjectRel]:
    return [
        rel
        for rel in model._meta.get_fields()
        if isinstance(rel, ForeignObjectRel)
        and f"{rel.field.model._meta.label}.{rel.field.name}" not in NOT_WALKED
    ]


def relation_label(rel: ForeignObjectRel) -> str:
    return f"{rel.field.model._meta.label}.{rel.field.name}"


def _breaks_uniqueness(rel: ForeignObjectRel) -> bool:
    """Whether moving this field can collide with a row the primary has."""
    field_name = rel.field.name
    if getattr(rel.field, "unique", False):
        return True
    meta = rel.field.model._meta
    if any(field_name in combo for combo in meta.unique_together):
        return True
    return any(field_name in (getattr(c, "fields", None) or []) for c in meta.constraints)


def _move_rows(
    rel: ForeignObjectRel,
    source: Model,
    target: Model,
    record: MergeRecord | None = None,
) -> tuple[int, list[Model]]:
    """Point rel at target instead of source. Returns moved count and casualties."""
    manager = rel.field.model._default_manager
    name = rel.field.name
    label = rel.field.model._meta.label

    if isinstance(rel, ManyToManyRel):
        moved = 0
        for row in manager.filter(**{name: source}):
            entries = getattr(row, name)
            # Whether the target was already in this set: if it was, adding it
            # changes nothing and the remove below is the only effect, so the
            # entry was destroyed rather than moved.
            already_held = entries.filter(pk=target.pk).exists()
            entries.add(target)
            entries.remove(source)
            if record is not None:
                record.linked(label, name, row.pk, source.pk, target.pk, already_held)
            moved += 1
        return moved, []

    rows = manager.filter(**{name: source})
    if not _breaks_uniqueness(rel):
        # One statement moves them all, so the identities have to be read
        # first: afterwards nothing distinguishes them from the target's own.
        pks = list(rows.values_list("pk", flat=True)) if record is not None else []
        count = rows.update(**{name: target})
        if record is not None:
            for pk in pks:
                record.moved(label, pk, name, source.pk, target.pk)
        return count, []

    rank = ROW_PREFERENCE.get(rel.field.model._meta.label)
    moved, casualties = 0, []
    for row in rows:
        # Kept so the row can be archived as it actually was. The setattr
        # below repoints it in memory whether or not the save succeeds, and
        # the snapshot is the only record of a row this merge destroys.
        original = getattr(row, f"{name}_id")
        setattr(row, name, target)
        try:
            with transaction.atomic():
                row.save(update_fields=[name])
            if record is not None:
                record.moved(label, row.pk, name, source.pk, target.pk)
            moved += 1
            continue
        except IntegrityError:
            pass

        # The primary already holds one. Keep whichever the model says is
        # better, rather than the primary's by default.
        theirs = _conflicting_row(rel, row, target)
        if rank is not None and theirs is not None and rank(row) > rank(theirs):
            # theirs was never repointed, so it archives as it stands.
            casualties.append(theirs)
            if record is not None:
                record.destroyed(theirs, "unique-clash")
            manager.filter(pk=theirs.pk).delete()
            setattr(row, name, target)
            with transaction.atomic():
                row.save(update_fields=[name])
            if record is not None:
                record.moved(label, row.pk, name, source.pk, target.pk)
            moved += 1
        else:
            # Put the owner back before archiving: this row belonged to the
            # account being absorbed, and a snapshot that names the survivor
            # instead would restore it onto the wrong person.
            setattr(row, f"{name}_id", original)
            casualties.append(row)
            if record is not None:
                record.destroyed(row, "unique-clash")
            manager.filter(pk=row.pk).delete()
    return moved, casualties


def _conflicting_row(rel: ForeignObjectRel, row: Model, target: Model) -> Model | None:
    """The row already on target that this one collides with."""
    manager = rel.field.model._default_manager
    name = rel.field.name
    combo = next((c for c in rel.field.model._meta.unique_together if name in c), None)
    lookup: dict[str, Any] = {name: target}
    for other in combo or ():
        if other != name:
            lookup[other] = getattr(row, other)
    return manager.filter(**lookup).first()


def _resolve_one_to_ones(
    primary_player: Player, duplicate_player: Player, record: MergeRecord | None = None
) -> list[Model]:
    """Move the better of two one-to-one rows onto the primary player."""
    casualties = []
    for label, rank in O2O_PREFERENCE.items():
        rel = next(
            (r for r in inbound_relations(Player) if r.field.model._meta.label == label), None
        )
        if rel is None:
            continue
        manager = rel.field.model._default_manager
        rows = list(manager.filter(**{f"{rel.field.name}__in": [primary_player, duplicate_player]}))
        if len(rows) < 2:  # noqa: PLR2004
            continue
        keep = max(rows, key=(lambda row: (rank(row), row.pk)))
        for row in rows:
            if row.pk != keep.pk:
                casualties.append(row)
                if record is not None:
                    record.destroyed(row, "o2o-clash")
                manager.filter(pk=row.pk).delete()
        was = getattr(keep, f"{rel.field.name}_id")
        setattr(keep, rel.field.name, primary_player)
        keep.save(update_fields=[rel.field.name])
        if record is not None and was != primary_player.pk:
            record.moved(label, keep.pk, rel.field.name, was, primary_player.pk)
    return casualties


def _move_outbound_m2m(source: Model, target: Model, record: MergeRecord | None = None) -> None:
    """M2M owned by the row being deleted, which the delete would drop.

    Player.teams is the one that matters: the through rows go with the row,
    and by the time the snapshot is taken they are already cascaded away, so
    a move that is not recorded here leaves no trace anywhere.
    """
    label = source._meta.label
    for m2m in source._meta.local_many_to_many:
        related = list(getattr(source, m2m.name).all())
        if not related:
            continue
        held = set(getattr(target, m2m.name).values_list("pk", flat=True))
        getattr(target, m2m.name).add(*related)
        if record is not None:
            for other in related:
                record.linked(label, m2m.name, other.pk, source.pk, target.pk, other.pk in held)


def _fill_blanks(
    target: Model, source: Model, names: tuple[str, ...], record: MergeRecord | None = None
) -> None:
    # target usually arrives as request.user, loaded before the row lock. A
    # bare save() would write back every column as that stale instance held
    # it - password included - reverting anything changed since. Save only
    # the fields this call actually filled.
    filled = []
    for name in names:
        was, incoming = getattr(target, name, None), getattr(source, name, None)
        if not was and incoming:
            setattr(target, name, incoming)
            filled.append(name)
            if record is not None:
                record.overwrote(target, name, was, incoming)
    if filled:
        target.save(update_fields=filled)


def references_to(model: type[Model], objects: Sequence[Model]) -> dict[str, int]:
    """Rows still pointing at these, by relation."""
    dangling: dict[str, int] = {}
    if not objects:
        return dangling
    for rel in inbound_relations(model):
        count = rel.field.model._default_manager.filter(
            **{f"{rel.field.name}__in": objects}
        ).count()
        if count:
            dangling[relation_label(rel)] = count
    return dangling


def find_references(users: list[User]) -> dict[str, int]:
    """Rows still pointing at these accounts or their players."""
    players = list(Player.objects.filter(user__in=users))
    return {**references_to(User, list(users)), **references_to(Player, players)}


def check_blockers(primary: User, duplicates: list[User]) -> list[str]:
    accounts = [primary, *duplicates]
    players = list(Player.objects.filter(user__in=accounts))
    blockers = []

    # Only an edge between two different accounts: a parent and child, not
    # the artifact of an account listed as its own player's guardian.
    if (
        Guardianship.objects.filter(user__in=accounts, player__in=players)
        .exclude(user=F("player__user"))
        .exists()
    ):
        blockers.append(BLOCK_GUARDIANSHIP)

    names = {normalize_name(user.first_name, user.last_name) for user in accounts}

    # Siblings: the guardian is not one of the accounts, so the edge misses them.
    if different_wards([player.id for player in players], names):
        blockers.append(BLOCK_DIFFERENT_WARDS)

    # Two people named differently, however they came to be grouped.
    if name_mismatch([(user.first_name, user.last_name) for user in accounts]):
        blockers.append(BLOCK_NAME_MISMATCH)

    # One child, two parents, and only one guardianship row can survive.
    if different_guardians([player.id for player in players]):
        blockers.append(BLOCK_DIFFERENT_GUARDIANS)

    if different_gender([player.gender for player in players]):
        blockers.append(BLOCK_DIFFERENT_GENDER)

    return blockers


def build_plan(primary: User, duplicates: list[User]) -> MergePlan:
    """Count what a merge would move and what it would destroy. Writes nothing.

    A clash cannot be counted from the duplicates alone: it depends on what
    the primary already holds, so each candidate row is checked against it.
    """
    plan = MergePlan(primary.id, [user.id for user in duplicates])
    players = list(Player.objects.filter(user__in=duplicates))
    primary_player = Player.objects.filter(user=primary).first()

    for model, objects, target in (
        (User, list(duplicates), primary),
        (Player, players, primary_player),
    ):
        if not objects:
            continue
        for rel in inbound_relations(model):
            rows = rel.field.model._default_manager.filter(**{f"{rel.field.name}__in": objects})
            if target is None or not _breaks_uniqueness(rel):
                plan.record(relation_label(rel), rows.count(), 0)
                continue

            rank = ROW_PREFERENCE.get(rel.field.model._meta.label)
            moved = collided = primary_loses = 0
            for row in rows:
                theirs = _conflicting_row(rel, row, target)
                if theirs is None:
                    moved += 1
                    continue
                collided += 1
                if rank is not None and rank(row) > rank(theirs):
                    primary_loses += 1
            plan.record(relation_label(rel), moved, collided, primary_loses)
    return plan


def _release_keeper(account: User, actor: User | None) -> None:
    """Undo what `account` proved as a keeper, now that it is being absorbed.

    A verification is proof for one keeper. Merged away, that keeper proves
    nothing about whoever absorbs it, so the account goes back to Open and
    any staff request it opened is closed.
    """
    rows = ClusterMember.objects.filter(
        Q(state=ClusterMember.State.VERIFIED, verified_by_id=account.pk)
        | Q(state=ClusterMember.State.PENDING_STAFF, staff_request__user=account)
    ).select_related("cluster", "staff_request")
    for row in rows:
        if row.staff_request is not None:
            close_request(row.staff_request, "The account that asked was merged into another")
        row.state = ClusterMember.State.OPEN
        row.verified_by_id = None
        row.verified_at = None
        row.proof = ""
        row.staff_request = None
        row.save(update_fields=["state", "verified_by_id", "verified_at", "proof", "staff_request"])
        log(row.cluster, ClusterEvent.Kind.KEEPER_MOVED, member=row, actor=actor, keeper=account.pk)


def _settle_group_rows(
    account: User,
    keeper: User,
    cluster: DuplicateCluster | None,
    merge: AccountMerge,
    actor: User | None,
) -> None:
    """Mark every group row of an absorbed account, instead of letting the
    relation walk move or delete it. Runs before the account is deleted.

    Any other group this leaves with nothing to merge is closed; the one the
    merge came from is its caller's to close.
    """
    elsewhere = set()
    for row in ClusterMember.objects.filter(user=account).select_related("cluster"):
        here = cluster is not None and row.cluster_id == cluster.pk
        row.state = ClusterMember.State.MERGED if here else ClusterMember.State.MERGED_ELSEWHERE
        row.merged_into_id = keeper.pk
        row.merge = merge
        row.user = None
        row.save(update_fields=["state", "merged_into_id", "merge", "user"])
        kind = ClusterEvent.Kind.MERGED if here else ClusterEvent.Kind.MERGED_ELSEWHERE
        log(row.cluster, kind, member=row, actor=actor, merge=merge.pk, into=keeper.pk)
        if not here:
            elsewhere.add(row.cluster_id)
    close_emptied(sorted(elsewhere), actor)


def merge_accounts(
    primary: User,
    duplicates: list[User],
    *,
    actor: User | None = None,
    matched_by: str = "",
    resolved: dict[str, Any] | None = None,
    dry_run: bool = True,
    cluster: DuplicateCluster | None = None,
    proof: dict[str, Any] | None = None,
) -> MergePlan:
    """Fold duplicates into primary, then delete them."""
    duplicates = [user for user in duplicates if user.pk != primary.pk]
    if not duplicates:
        raise MergeBlockedError(["nothing-to-merge"])

    blockers = check_blockers(primary, duplicates)
    if blockers:
        raise MergeBlockedError(blockers)

    if dry_run:
        return build_plan(primary, duplicates)

    plan = MergePlan(primary.id, [user.id for user in duplicates])
    record = MergeRecord()

    with transaction.atomic():
        # Held for the whole merge, before anything is read. The dangling
        # reference check near the end is a plain SELECT, so a merge that
        # commits between that check and the delete would have its rows
        # cascade away unnoticed - and nothing else stops two merges sharing
        # an account, least of all the management command, which until now
        # took no lock at all. Ordered by pk so two of them cannot deadlock.
        # A no-op on SQLite, which is why no test can prove it works; the
        # test suite is SQLite and production is Postgres.
        list(
            User.objects.select_for_update()
            .filter(pk__in=[primary.pk, *(user.pk for user in duplicates)])
            .order_by("pk")
        )

        for duplicate in duplicates:
            _release_keeper(duplicate, actor)
        record.proof = proof or {}

        casualties: list[Model] = []
        # Read before anything below deletes or repoints one: _apply_resolved
        # needs these accounts' own pristine values, and the snapshot needs
        # the rows as they stood before the merge touched them.
        duplicate_players = list(Player.objects.filter(user__in=duplicates))
        snapshot_rows: list[Model] = [*duplicates, *duplicate_players]

        # A profile that went in has to come out, on the surviving account.
        expects_player = Player.objects.filter(user__in=[primary, *duplicates]).exists()

        primary_player = Player.objects.filter(user=primary).first()
        for duplicate in duplicates:
            duplicate_player = Player.objects.filter(user=duplicate).first()
            if duplicate_player is None:
                continue
            if primary_player is None:
                # Keeping the emptier account is common; move the profile
                # across instead of letting the delete cascade take it.
                record.moved(
                    Player._meta.label, duplicate_player.pk, "user", duplicate.pk, primary.pk
                )
                duplicate_player.user = primary
                duplicate_player.save(update_fields=["user"])
                primary_player = duplicate_player
                continue

            casualties += _resolve_one_to_ones(primary_player, duplicate_player, record)
            for rel in inbound_relations(Player):
                moved, lost = _move_rows(rel, duplicate_player, primary_player, record)
                casualties += lost
                plan.record(relation_label(rel), moved, len(lost))
            _move_outbound_m2m(duplicate_player, primary_player, record)
            # Checked here rather than after the merge: once the row is gone
            # so is anything the walk failed to move, and the cascade would
            # have taken it silently.
            stuck = references_to(Player, [duplicate_player])
            if stuck:
                raise MergeIncompleteError(stuck)

            # After the delete, so a unique field like ultimate_central_id is
            # not held by two rows at once. The instance keeps its values.
            record.destroyed(duplicate_player, "explicit")
            duplicate_player.delete()
            _fill_blanks(primary_player, duplicate_player, PLAYER_FILLABLE, record)

        for duplicate in duplicates:
            for rel in inbound_relations(User):
                moved, lost = _move_rows(rel, duplicate, primary, record)
                casualties += lost
                plan.record(relation_label(rel), moved, len(lost))
            _move_outbound_m2m(duplicate, primary, record)

        emails = [user.email for user in duplicates if user.email]
        for duplicate in duplicates:
            _fill_blanks(primary, duplicate, USER_FILLABLE, record)

        if resolved:
            _apply_resolved(
                primary, primary_player, duplicates, duplicate_players, resolved, record
            )

        dangling = find_references(duplicates)
        if dangling:
            raise MergeIncompleteError(dangling)

        surviving = Player.objects.filter(user=primary).count()
        if expects_player and surviving != 1:
            raise MergeIncompleteError({"players-on-the-surviving-account": surviving})

        # Before the record is written, so that an address taken off another
        # account is in it. Afterwards would be too late to say so.
        for address, held_by in EmailAlias.remember(emails, primary):
            record.aliased(address, primary.pk, held_by)

        # These two deletes are the last thing that happens and cannot fail
        # independently of the rest, so they are recorded here where the
        # record is still being written rather than after it is stored.
        for duplicate in duplicates:
            record.destroyed(duplicate, "explicit")

        merge = AccountMerge.objects.create(
            primary_user=primary,
            merged_by=actor,
            actor_id=actor.pk if actor is not None else None,
            actor_email=actor.email if actor is not None else "",
            matched_by=matched_by,
            duplicate_user_ids=[user.id for user in duplicates],
            duplicate_emails=emails,
            plan=plan.as_dict(),
            record=record.as_dict(),
            snapshot=_snapshot([*snapshot_rows, *casualties]),
            cluster=cluster,
            primary_id=primary.pk,
            primary_email=primary.email,
        )

        for duplicate in duplicates:
            _settle_group_rows(duplicate, primary, cluster, merge, actor)

        for duplicate in duplicates:
            duplicate.delete()

    plan.merge_id = merge.id
    return plan
