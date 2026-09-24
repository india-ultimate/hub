"""Turning detected duplicates into clusters people can act on."""

from collections import defaultdict
from collections.abc import Iterable

from django.db import transaction
from django.db.models import Count, Q
from django.utils.timezone import now

from server.core.models import User
from server.duplicates.detect import Cluster, find_clusters
from server.duplicates.history import log
from server.duplicates.models import ClusterEvent, ClusterMember, DuplicateCluster


def _open_user_ids() -> set[int]:
    """Accounts already waiting on an answer, which must not be asked twice."""
    return set(
        ClusterMember.objects.filter(
            cluster__status__in=DuplicateCluster.OPEN_STATUSES
        ).values_list("user_id", flat=True)
    )


def _dismissed_groups() -> set[frozenset[int | None]]:
    """Exactly the groups someone has said are not one person.

    Held as whole groups rather than loose account ids: "these three are not
    the same person" says nothing about a different pairing one of them turns
    up in later, and treating it as if it did hid those accounts for good.
    """
    members: dict[int, set[int | None]] = defaultdict(set)
    # The frozen account id, not user: a merge or a deletion clears user,
    # and the group would stop saying which accounts it was about.
    for cluster_id, account_id in ClusterMember.objects.filter(
        cluster__status=DuplicateCluster.Status.DISMISSED
    ).values_list("cluster_id", "account_id"):
        members[cluster_id].add(account_id)
    return {frozenset(ids) for ids in members.values()}


def close_if_done(cluster: DuplicateCluster, actor: User | None) -> bool:
    """Closed once fewer than two accounts could still be merged — so a group
    of a keeper and a deleted account closes too. The caller holds the
    group's lock. Says whether this call closed it."""
    live = cluster.members.filter(user__isnull=False, state__in=ClusterMember.MERGEABLE).count()
    if live >= 2 or not cluster.is_open:  # noqa: PLR2004
        return False
    cluster.status = DuplicateCluster.Status.RESOLVED
    cluster.resolved_at = now()
    cluster.save(update_fields=["status", "resolved_at"])
    log(cluster, ClusterEvent.Kind.CLOSED, actor=actor)
    return True


def _lock_if_free(cluster_id: int) -> DuplicateCluster | None:
    # no_key, as in flow._lock: FOR UPDATE would block the key-share check
    # another merge's events make on this group when that merge commits.
    return (
        DuplicateCluster.objects.select_for_update(skip_locked=True, no_key=True)
        .filter(pk=cluster_id)
        .first()
    )


def _close(cluster_id: int, actor: User | None) -> bool:
    """Close a group if it is done, in its own transaction, waiting for its
    lock. Only where no account locks are held."""
    with transaction.atomic():
        return close_if_done(
            DuplicateCluster.objects.select_for_update(no_key=True).get(pk=cluster_id), actor
        )


def close_emptied(cluster_ids: Iterable[int], actor: User | None) -> None:
    """Close the other groups a merge has left with nothing to merge, so they
    stop holding their accounts back from detection and stop showing on the
    Dashboard.

    The merge holds its accounts' locks by now, and a group's lock comes
    before accounts', so it must not wait for one: whoever holds the group
    may be waiting for one of those accounts. A group nobody holds is closed
    here, in the merge's transaction; one somebody holds is closed once the
    merge commits, when waiting is safe. A no-op on SQLite, where nothing is
    ever held, which is why no test can show the wait; production is
    Postgres.

    The close after the commit is robust, so its failure is logged instead
    of turning a finished merge into a 500 and skipping the merge's emails;
    close_finished catches the group on the next detection run.
    """
    for cluster_id in cluster_ids:
        cluster = _lock_if_free(cluster_id)
        if cluster is not None:
            close_if_done(cluster, actor)
            continue

        # A function, not functools.partial: Django reports a robust
        # callback's failure by its __qualname__, which a partial lacks.
        def close_later(cluster_id: int = cluster_id) -> None:
            _close(cluster_id, actor)

        transaction.on_commit(close_later, robust=True)


def close_finished() -> int:
    """Close every open group left with fewer than two accounts to merge, and
    say how many.

    A merge closes the groups it empties, but one it could only close after
    its commit stays open if that close fails or the process stops first,
    and nothing else would ever look at it again. Safe to run twice: each
    group is checked again under its lock, so none is closed, or given its
    closed event, twice.
    """
    live = Count(
        "members",
        filter=Q(members__user__isnull=False, members__state__in=ClusterMember.MERGEABLE),
    )
    finished = (
        DuplicateCluster.objects.filter(status__in=DuplicateCluster.OPEN_STATUSES)
        .annotate(live=live)
        .filter(live__lt=2)
        .values_list("pk", flat=True)
    )
    return sum(_close(cluster_id, None) for cluster_id in list(finished))


@transaction.atomic
def create_clusters(clusters: list[Cluster]) -> list[DuplicateCluster]:
    """Persist mergeable clusters, skipping anyone already waiting on one.

    A group someone has dismissed must not come back round, but only that
    group: the accounts in it are free to appear in a different one.

    Groups left open with nothing to merge are closed first, so every
    detection run, the command's included, also sweeps those up and frees
    their accounts.
    """
    close_finished()
    spoken_for = _open_user_ids()
    dismissed = _dismissed_groups()
    created = []

    for cluster in clusters:
        if not cluster.is_mergeable:
            continue
        user_ids = [member.user_id for member in cluster.members]
        if any(user_id in spoken_for for user_id in user_ids):
            continue
        if frozenset(user_ids) in dismissed:
            continue

        record = DuplicateCluster.objects.create(matched_by=" ".join(sorted(cluster.rules)))
        users = User.objects.filter(id__in=user_ids).order_by("id")
        ClusterMember.objects.bulk_create([ClusterMember.of(record, user) for user in users])
        log(record, ClusterEvent.Kind.DETECTED, rules=record.matched_by)
        spoken_for.update(user_ids)
        created.append(record)

    return created


def detect_and_create() -> list[DuplicateCluster]:
    return create_clusters(find_clusters())
