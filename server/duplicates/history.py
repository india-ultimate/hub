"""The one way a group's timeline is written."""

from server.core.models import User
from server.duplicates.models import ClusterEvent, ClusterMember, DuplicateCluster


def log(
    cluster: DuplicateCluster,
    kind: str,
    *,
    member: ClusterMember | None = None,
    actor: User | None = None,
    **detail: object,
) -> ClusterEvent:
    """Append one event. Call it in the same transaction as the change it
    describes, so the change cannot commit without it. Never pass a code."""
    return ClusterEvent.objects.create(
        cluster=cluster,
        member=member,
        kind=kind,
        actor_id=actor.pk if actor is not None else None,
        actor_email=actor.email if actor is not None else "",
        detail=detail,
    )
