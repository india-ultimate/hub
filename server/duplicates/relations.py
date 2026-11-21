"""Moving the rows that point at a merged object onto the one that stays.

Shared by every kind of merge. Relations are walked at runtime rather than
listed, because a list goes stale and a model missing from it is not skipped,
it is cascade-deleted; references_to then proves nothing was left behind.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Model
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.fields.reverse_related import ManyToManyRel


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


class MergeIncompleteError(Exception):
    """Rows still point at an account about to be deleted."""


# History, not ownership. A group row says who was in the group; moving it to
# the keeper, or deleting it on a clash, would erase that. _settle_group_rows
# handles these explicitly instead, and the dangling-reference guard skips
# them because it walks the same list.
NOT_WALKED = frozenset(
    {
        "server.ClusterMember.user",
        # The link row carries a tier, an amount and the subscription it bought.
        # Moving it as a many-to-many would .add() a fresh empty row and
        # .remove() the one holding all of that. The through model's own
        # player foreign key is walked instead, which repoints the real row.
        "server.RazorpayTransaction.players",
    }
)


def inbound_relations(model: type[Model]) -> list[ForeignObjectRel]:
    return [
        rel
        for rel in model._meta.get_fields()
        if isinstance(rel, ForeignObjectRel)
        and f"{rel.field.model._meta.label}.{rel.field.name}" not in NOT_WALKED
    ]


def relation_label(rel: ForeignObjectRel) -> str:
    return f"{rel.field.model._meta.label}.{rel.field.name}"


def breaks_uniqueness(rel: ForeignObjectRel) -> bool:
    """Whether moving this field can collide with a row the primary has."""
    field_name = rel.field.name
    if getattr(rel.field, "unique", False):
        return True
    return any(field_name in combo for combo in rel.field.model._meta.unique_together)


def move_rows(
    rel: ForeignObjectRel,
    source: Model,
    target: Model,
    record: MergeRecord | None = None,
    prefer: Mapping[str, Callable[[Any], Any]] | None = None,
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
    if not breaks_uniqueness(rel):
        # One statement moves them all, so the identities have to be read
        # first: afterwards nothing distinguishes them from the target's own.
        pks = list(rows.values_list("pk", flat=True)) if record is not None else []
        count = rows.update(**{name: target})
        if record is not None:
            for pk in pks:
                record.moved(label, pk, name, source.pk, target.pk)
        return count, []

    rank = (prefer or {}).get(rel.field.model._meta.label)
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
            # The only failure understood here is a clash with a row the
            # primary already holds. Anything else - a different constraint,
            # a trigger, a clash no row can be named for - would otherwise
            # fall through to the casualty path below, which deletes a row.
            theirs = conflicting_row(rel, row, target)
            if theirs is None:
                raise

        # The primary already holds one. Keep whichever the model says is
        # better, rather than the primary's by default.
        if rank is not None and rank(row) > rank(theirs):
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


def conflicting_row(rel: ForeignObjectRel, row: Model, target: Model) -> Model | None:
    """The row already on target that this one collides with."""
    manager = rel.field.model._default_manager
    name = rel.field.name
    combo = next((c for c in rel.field.model._meta.unique_together if name in c), None)
    lookup: dict[str, Any] = {name: target}
    for other in combo or ():
        if other != name:
            lookup[other] = getattr(row, other)
    return manager.filter(**lookup).first()


def fill_blanks(
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
