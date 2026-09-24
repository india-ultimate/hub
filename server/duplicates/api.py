"""The page a person lands on from the duplicate-accounts email."""

from django.db.models import Max
from django.http import HttpRequest
from ninja import Router

from server.core.models import Player, User
from server.duplicates.flow import (
    FlowError,
    dismiss,
    membership,
    merge_pair,
    request_merge,
    request_staff,
    send_code,
    verify_code,
    verify_same_inbox,
)
from server.duplicates.identity import mask_email
from server.duplicates.merge import (
    MergeBlockedError,
    MergeFieldError,
    MergeIncompleteError,
    resolvable_fields,
)
from server.duplicates.models import ClusterEvent, ClusterMember, DuplicateCluster
from server.duplicates.schema import (
    GroupSchema,
    MergeConfirmSchema,
    MergeResultSchema,
    MyGroupSchema,
    RequestedSchema,
    RequestMergeSchema,
    RowActionSchema,
    StaffRequestSchema,
    VerifySchema,
)
from server.types import message_response

router = Router()


class AuthenticatedHttpRequest(HttpRequest):
    user: User


def _member_or_404(token: str) -> ClusterMember | None:
    return ClusterMember.objects.select_related("cluster", "user").filter(claim_token=token).first()


def _profiles(users: list[User]) -> dict[int, dict[str, object]]:
    """Each account's own answer for the fields the review step can set."""
    user_fields, player_fields = resolvable_fields()
    players = {p.user_id: p for p in Player.objects.filter(user__in=users)}

    profiles = {}
    for user in users:
        values: dict[str, object] = {name: getattr(user, name) for name in user_fields}
        player = players.get(user.id)
        if player is not None:
            values.update({name: getattr(player, name) for name in player_fields})
        profiles[user.id] = values
    return profiles


def _row_state(row: ClusterMember) -> str:
    return "gone" if row.is_gone else row.state


def _visible_rows(
    cluster: DuplicateCluster, rows: list[ClusterMember], mine: ClusterMember | None
) -> list[ClusterMember]:
    """Status is shown widely; a finished group shows only what the viewer
    is entitled to (spec §5)."""
    if cluster.status == DuplicateCluster.Status.DISMISSED:
        return [mine] if mine is not None else []
    if cluster.status == DuplicateCluster.Status.RESOLVED:
        return rows if mine is not None else []
    return rows


def _serialize(link: ClusterMember, viewer: User | None) -> dict[str, object]:
    cluster = link.cluster
    mine = membership(cluster, viewer)
    if viewer is not None and mine is not None and cluster.is_open and not mine.is_expired:
        verify_same_inbox(cluster, viewer)
    rows = list(cluster.members.select_related("user").order_by("id"))
    since = dict(
        ClusterEvent.objects.filter(cluster=cluster, member__isnull=False)
        .values("member_id")
        .annotate(latest=Max("at"))
        .values_list("member_id", "latest")
    )
    viewer_id = viewer.pk if viewer is not None and mine is not None else None

    def detailed(row: ClusterMember) -> bool:
        if viewer_id is None:
            return False
        return (
            row.user_id == viewer_id
            or row.merged_into_id == viewer_id
            or (row.state == ClusterMember.State.VERIFIED and row.verified_by_id == viewer_id)
        )

    requested = cluster.origin == DuplicateCluster.Origin.REQUESTED

    def shows_address(row: ClusterMember) -> bool:
        """Spec §4. In a group detection built, any signed-in member sees
        every row's address: two masked Gmail addresses can read
        identically, and telling the accounts apart is the whole point.

        A requested group is not that. The requester chose the other member
        by typing an address, `request_merge` resolves it through
        `EmailAlias`, and the account's own address is then one they never
        typed — so reading it back would turn any absorbed address into a
        lookup for the current one. There the address opens up on proof,
        like the profile: their own row, an account merged into theirs, or
        one they confirmed with a code sent to it.
        """
        return (viewer_id is not None and not requested) or detailed(row)

    shown = _visible_rows(cluster, rows, mine)
    live_users = [row.user for row in shown if row.user is not None and detailed(row)]
    profiles = _profiles(live_users) if live_users else {}
    is_requester = viewer_id is not None and cluster.requested_by_id == viewer_id
    # dismissed_by is the discriminator: is_requester alone is true whether
    # the requester cancelled or the other owner dismissed (spec §12).
    cancelled_by_you = mine is not None and cluster.dismissed_by_id == mine.pk and is_requester
    # Last sign in is how a member recognises their own old account in a
    # group detection found. In a requested group the address was typed,
    # and anyone can type anyone's, so it would only tell them about a
    # stranger.
    show_last_seen = mine is not None and not requested
    return {
        "token": link.claim_token,
        "status": cluster.status,
        "origin": cluster.origin,
        "expires_at": link.expires_at,
        "signed_in_as": viewer_id,
        "signed_in_elsewhere": viewer.email if viewer is not None and mine is None else None,
        "is_requester": is_requester,
        "cancelled_by_you": cancelled_by_you,
        "can_act": mine is not None and cluster.is_open and not mine.is_expired,
        # Whether a merge ever happened in this group, regardless of what
        # the viewer can see — a finished group with no visible rows still
        # needs to say this much honestly (spec §13).
        "anything_merged": any(row.state == ClusterMember.State.MERGED for row in rows),
        "rows": [
            {
                "row_id": row.pk,
                "user_id": row.user_id,
                "email": row.account_email if shows_address(row) else mask_email(row.account_email),
                "state": _row_state(row),
                "since": since.get(row.pk),
                "is_yours": viewer_id is not None and row.user_id == viewer_id,
                "merged_into_you": viewer_id is not None and row.merged_into_id == viewer_id,
                "verified_for_you": viewer_id is not None
                and row.state == ClusterMember.State.VERIFIED
                and row.verified_by_id == viewer_id,
                # Gated: "same inbox" under two masked rows would tell a
                # signed-out link holder they share one mailbox.
                "proof": row.proof if viewer_id is not None else "",
                "last_seen": (
                    row.user.last_login.strftime("%b %Y")
                    if show_last_seen and row.user is not None and row.user.last_login
                    else None
                ),
                "profile": profiles.get(row.user_id) if row.user_id else None,
            }
            for row in shown
        ],
    }


def _viewer(request: HttpRequest) -> User | None:
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


@router.get("/mine", response={200: list[MyGroupSchema]})
def my_groups(request: AuthenticatedHttpRequest) -> tuple[int, list[dict[str, object]]]:
    rows = ClusterMember.objects.filter(
        user=request.user, cluster__status__in=DuplicateCluster.OPEN_STATUSES
    ).select_related("cluster")
    return 200, [
        {
            "token": row.claim_token,
            "origin": row.cluster.origin,
            "waiting": row.cluster.members.exclude(user=request.user)
            .filter(user__isnull=False, state__in=ClusterMember.MERGEABLE)
            .count(),
        }
        for row in rows
    ]


@router.post("", response={200: RequestedSchema, 400: message_response, 404: message_response})
def start_merge(
    request: AuthenticatedHttpRequest, payload: RequestMergeSchema
) -> tuple[int, dict[str, str]]:
    try:
        row = request_merge(request.user, payload.email, payload.note)
    except FlowError as refused:
        return refused.status, {"message": str(refused)}
    return 200, {"token": row.claim_token}


@router.get("/{token}", auth=None, response={200: GroupSchema, 404: message_response})
def get_cluster(request: HttpRequest, token: str) -> tuple[int, object]:
    link = _member_or_404(token)
    if link is None:
        return 404, {"message": "This link is not valid any more"}
    viewer = _viewer(request)
    is_member = membership(link.cluster, viewer) is not None
    # Expiry stops actions, not viewing — for members. Anyone else holding
    # an expired link to an open group gets nothing, as before.
    if link.is_expired and link.cluster.is_open and not is_member:
        return 404, {"message": "This link is not valid any more"}
    return 200, _serialize(link, viewer)


@router.post(
    "/{token}/confirm",
    response={
        200: MergeResultSchema,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def confirm_merge(
    request: AuthenticatedHttpRequest, token: str, payload: MergeConfirmSchema
) -> tuple[int, object]:
    try:
        plan = merge_pair(
            _group(token),
            request.user,
            payload.absorb_user_id,
            actor=request.user,
            resolved=payload.resolved,
        )
    except FlowError as refused:
        return refused.status, {"message": str(refused)}
    except MergeBlockedError as blocked:
        reasons = ", ".join(blocked.args[0])
        return 400, {
            "message": f"These look like different people ({reasons}). "
            "If they really are both yours, ask our team to review.",
            # The page offers that review on this row only when told why.
            "reason": "blocked",
        }
    except MergeFieldError as invalid:
        return 400, {"message": str(invalid)}
    except MergeIncompleteError:
        return 400, {"message": "We could not merge these safely, so nothing was changed"}
    return 200, {
        "primary_user_id": request.user.id,
        "merged_user_ids": [payload.absorb_user_id],
        "rows_moved": plan.rows_moved,
    }


@router.post(
    "/{token}/dismiss",
    response={
        200: message_response,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def dismiss_cluster(request: AuthenticatedHttpRequest, token: str) -> tuple[int, message_response]:
    try:
        return 200, {"message": dismiss(_group(token), request.user)}
    except FlowError as refused:
        return refused.status, {"message": str(refused)}


def _group(token: str) -> DuplicateCluster:
    member = _member_or_404(token)
    if member is None:
        raise FlowError("This link is not valid any more", 404)
    return member.cluster


@router.post(
    "/{token}/code",
    response={
        200: message_response,
        400: message_response,
        403: message_response,
        404: message_response,
        503: message_response,
    },
)
def ask_for_code(
    request: AuthenticatedHttpRequest, token: str, payload: RowActionSchema
) -> tuple[int, message_response]:
    try:
        send_code(_group(token), request.user, payload.user_id)
    except FlowError as refused:
        return refused.status, {"message": str(refused)}
    return 200, {"message": "We've emailed a code to that account"}


@router.post(
    "/{token}/verify",
    response={
        200: message_response,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def check_code(
    request: AuthenticatedHttpRequest, token: str, payload: VerifySchema
) -> tuple[int, message_response]:
    try:
        verify_code(_group(token), request.user, payload.user_id, payload.code)
    except FlowError as refused:
        return refused.status, {"message": str(refused)}
    return 200, {"message": "Confirmed"}


@router.post(
    "/{token}/staff",
    response={
        200: message_response,
        400: message_response,
        403: message_response,
        404: message_response,
    },
)
def ask_our_team(
    request: AuthenticatedHttpRequest, token: str, payload: StaffRequestSchema
) -> tuple[int, message_response]:
    try:
        request_staff(_group(token), request.user, payload.user_id, payload.note)
    except FlowError as refused:
        return refused.status, {"message": str(refused)}
    return 200, {"message": "Sent to our team. We'll email you when it's decided"}
