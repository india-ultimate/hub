"""Everything a person or staff can do to a group, and what it changes.

The API and the admin are thin wrappers over these. Each action checks who
is asking, changes state and writes its event in one transaction.
"""

import datetime
from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils.timezone import now

from server.core.accounts import find_login_user
from server.core.models import Player, User
from server.duplicates import codes
from server.duplicates.clusters import close_if_done
from server.duplicates.emails import (
    PROOF_WORDS,
    notify_kept,
    notify_merged,
    notify_staff_event,
    send_code_email,
)
from server.duplicates.history import log
from server.duplicates.identity import normalize_email
from server.duplicates.merge import INBOX_PROOFS, MergePlan, merge_accounts
from server.duplicates.models import ClusterEvent, ClusterMember, DuplicateCluster
from server.duplicates.staff import close_request
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType


class FlowError(Exception):
    """Refused, with a reason the page can show and an HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def membership(cluster: DuplicateCluster, user: User | None) -> ClusterMember | None:
    if user is None:
        return None
    return cluster.members.filter(user=user).first()


def _lock(cluster: DuplicateCluster, *user_ids: int | None) -> DuplicateCluster:
    """The group as it is now, locked with these accounts until the caller's
    transaction ends. Call it first, inside transaction.atomic(), and read
    the rows you will change only after it, through _rows, require_keeper or
    other_row, which lock each row as they read it.

    Every function that changes a group or its rows does this. Without it,
    two requests each read a row, decide, and write back, and the later
    write quietly undoes the earlier one: a dismissal over a finished merge,
    or a staff rejection over an account already merged.

    The order: the group, then accounts in pk order (as merge_accounts takes
    them), then group rows. Anything written for a keeper locks that keeper,
    so a merge absorbing them elsewhere either sees it and undoes it, or
    runs first and leaves them nothing to write it for.

    A merge breaks that order for the other groups its accounts are in: it
    already holds the accounts when it rewrites their rows there, writes
    their merged-elsewhere events and closes them. Two things keep that from
    deadlocking against someone holding one of those groups while they wait
    for the same account:
    - Rows are locked last, after accounts, so nobody waiting for an account
      holds a row the merge needs.
    - The group itself is locked FOR NO KEY UPDATE (no_key=True). The events'
      foreign key to the group is checked at COMMIT with FOR KEY SHARE,
      because Django makes Postgres foreign keys DEFERRABLE INITIALLY
      DEFERRED; FOR UPDATE blocks that check, and the merge could then never
      commit. FOR NO KEY UPDATE still keeps every other _lock out.
    Closing another group never waits for it either; see close_emptied.

    A no-op on SQLite, so the SQLite suite cannot show any of this;
    TestRacingAMergeOnPostgres does, when the suite is pointed at Postgres.
    """
    locked = DuplicateCluster.objects.select_for_update(no_key=True).get(pk=cluster.pk)
    accounts = sorted({pk for pk in user_ids if pk is not None})
    if accounts:
        list(User.objects.select_for_update().filter(pk__in=accounts).order_by("pk"))
    return locked


def _rows(cluster: DuplicateCluster) -> QuerySet[ClusterMember]:
    """The group's rows, each locked as it is read. Only after _lock."""
    # of=("self",): Postgres cannot lock the nullable side of the outer join
    # that select_related("user") makes, and the row is what changes anyway.
    return cluster.members.select_for_update(of=("self",))


def require_keeper(
    cluster: DuplicateCluster, keeper: User, *, for_staff: bool = False
) -> ClusterMember:
    """The signed-in person's own row, if they may act in this group.

    Expiry is their own row's: a link finds the group, it does not grant
    anything. Staff approval ignores it — a request waiting on staff never
    expires.
    """
    row = _rows(cluster).filter(user=keeper).first()
    if row is None:
        raise FlowError("Sign in to one of the accounts in this group", 403)
    if not cluster.is_open:
        raise FlowError("These accounts have already been sorted out")
    if row.is_expired and not for_staff:
        raise FlowError("This link has expired")
    return row


def other_row(cluster: DuplicateCluster, keeper: User, user_id: int) -> ClusterMember:
    """Another account in the group that could still be merged."""
    if user_id == keeper.pk:
        raise FlowError("That's the account you're keeping")
    row = _rows(cluster).filter(user_id=user_id).select_related("user").first()
    if row is None or row.state not in ClusterMember.MERGEABLE:
        raise FlowError("That account is not part of this group any more")
    return row


def _mark_verified(row: ClusterMember, keeper: User, proof: str) -> None:
    if row.staff_request is not None:
        close_request(row.staff_request, "Confirmed with a code instead")
    row.state = ClusterMember.State.VERIFIED
    row.verified_by_id = keeper.pk
    row.verified_at = now()
    row.proof = proof
    row.staff_request = None
    row.save(update_fields=["state", "verified_by_id", "verified_at", "proof", "staff_request"])
    log(row.cluster, ClusterEvent.Kind.CODE_VERIFIED, member=row, actor=keeper, proof=proof)


def verify_same_inbox(cluster: DuplicateCluster, keeper: User) -> None:
    """Signing in already proved the keeper's inbox, so an account on the
    same address needs no code. Runs when a member opens the page."""
    with transaction.atomic():
        cluster = _lock(cluster, keeper.pk)
        mine = _rows(cluster).filter(user=keeper).first()
        if mine is None or not cluster.is_open or mine.is_expired:
            return
        kept = normalize_email(keeper.email)
        # Signing in proves an inbox only if there is one to prove. An account
        # can hold a blank address or a name slug (register_ward,
        # import_players), and two of those normalise equal, so a name+dob
        # group of them would confirm itself and merge with no code and no
        # staff. Same test request_merge and build_messages use: no @, no
        # address. Guarding the keeper covers both sides — anything equal to
        # an address with an @ has one too.
        if "@" not in kept:
            return
        rows = (
            _rows(cluster)
            .exclude(pk=mine.pk)
            .filter(
                user__isnull=False,
                state__in=[ClusterMember.State.OPEN, ClusterMember.State.REJECTED],
            )
        )
        for row in rows.select_related("user"):
            if row.user is not None and normalize_email(row.user.email) == kept:
                _mark_verified(row, keeper, ClusterMember.Proof.SAME_INBOX)


def send_code(cluster: DuplicateCluster, keeper: User, user_id: int) -> None:
    with transaction.atomic():
        # Both accounts locked: the day's limits count code-sent events, so
        # two sends to one account or by one person must not both count the
        # same events and both pass. The event is written before the locks
        # are let go.
        cluster = _lock(cluster, keeper.pk, user_id)
        require_keeper(cluster, keeper)
        row = other_row(cluster, keeper, user_id)
        if row.state == ClusterMember.State.VERIFIED and row.verified_by_id == keeper.pk:
            raise FlowError("That account is already confirmed")
        try:
            codes.check_budget(user_id, keeper)
        except codes.CodeError as error:
            raise FlowError(str(error)) from error
        code = codes.issue(row, keeper)
        log(cluster, ClusterEvent.Kind.CODE_SENT, member=row, actor=keeper)
    # Sent once the code and its event are committed, so no email carries a
    # code that was not stored and logged. A failed send still counts: the
    # code exists and can be guessed at whether or not its email arrived, so
    # refunding it would let a failing mail server hand out free guesses.
    # The event says a code was issued and its email attempted; both hold.
    try:
        send_code_email(row, keeper, code)
    except OSError as error:  # SMTPException is an OSError, as are socket errors
        raise FlowError("We couldn't send the code just now. Try again in a minute", 503) from error


def verify_code(cluster: DuplicateCluster, keeper: User, user_id: int, code: str) -> None:
    with transaction.atomic():
        cluster = _lock(cluster, keeper.pk, user_id)
        require_keeper(cluster, keeper)
        row = other_row(cluster, keeper, user_id)
        error = codes.check(row, keeper, code)
        if error is None:
            _mark_verified(row, keeper, ClusterMember.Proof.EMAIL_CODE)
        else:
            kind = ClusterEvent.Kind.CODE_LOCKED if error.locked else ClusterEvent.Kind.CODE_FAILED
            log(cluster, kind, member=row, actor=keeper, attempts=row.code_attempts)
    # Raised only after the attempt and its event are committed together;
    # raised inside, it would roll back the very attempt it reports.
    if error is not None:
        raise FlowError(str(error)) from error


def dismiss(cluster: DuplicateCluster, user: User) -> str:
    """ "These aren't the same person": ends the group for every member.

    For the person who started a requested group this is cancelling it,
    which spec §12 allows "while nothing in it has merged". A requested group
    holds two accounts and closes on its merge, so refusing a finished group
    is that rule. Expiry does not stop it (§11 names what expiry stops): a
    request waiting on our team never expires, and the other account's
    owner must still be able to say no before staff act.
    """
    with transaction.atomic():
        cluster = _lock(cluster)
        row = _rows(cluster).filter(user=user).first()
        if row is None:
            raise FlowError("Sign in to one of the accounts in this group", 403)
        if not cluster.is_open:
            raise FlowError("These accounts have already been sorted out")
        cancelling = (
            cluster.origin == DuplicateCluster.Origin.REQUESTED
            and cluster.requested_by_id == user.pk
        )
        cluster.status = DuplicateCluster.Status.DISMISSED
        cluster.resolved_at = now()
        cluster.dismissed_by = row
        cluster.save(update_fields=["status", "resolved_at", "dismissed_by"])
        cluster.members.update(expires_at=now())
        for pending in cluster.members.filter(
            state=ClusterMember.State.PENDING_STAFF
        ).select_related("staff_request"):
            if pending.staff_request is not None:
                close_request(pending.staff_request, "The group was dismissed")
        kind = ClusterEvent.Kind.CANCELLED if cancelling else ClusterEvent.Kind.DISMISSED
        log(cluster, kind, member=row, actor=user)
    if cancelling:
        return "Your request is cancelled"
    return "Thanks, we won't ask about these accounts again"


MAX_OPEN_REQUESTS = 3
# Requests one person can start in a day, cancelled ones included, so that
# cancelling and asking again is not a way round MAX_OPEN_REQUESTS.
MAX_REQUESTS_PER_DAY = 5


def request_merge(keeper: User, email: str, note: str) -> ClusterMember:
    """Start a group for the keeper and one other account. Returns the
    keeper's row, whose link is the group's page."""
    # Before resolving, because sign in resolves a username exactly and an
    # account registered without an address has a name slug for one
    # (register_ward, import_players). Typing a stranger's name would
    # otherwise make the caller a member of that stranger's group. Refused
    # in the same words as an unknown address, so this stays a non-oracle.
    if "@" not in email.strip():
        raise FlowError("We couldn't find an account with that email address.", 404)
    other = find_login_user(email)
    if other is None:
        raise FlowError("We couldn't find an account with that email address.", 404)
    if other.pk == keeper.pk:
        raise FlowError("That address already belongs to this account.")

    with transaction.atomic():
        # So two requests at once cannot both count below a limit, or both
        # miss a shared group the other is about to create. Both accounts,
        # not just the keeper: otherwise these two people asking about each
        # other at the same moment each lock their own row, block on
        # nothing, and open a group apiece for the same pair. In pk order,
        # as _lock and merge_accounts take them. A no-op on SQLite;
        # production is Postgres.
        list(
            User.objects.select_for_update()
            .filter(pk__in=sorted({keeper.pk, other.pk}))
            .order_by("pk")
        )
        # Read again now the lock is held, before anything is counted or
        # decided: a merge that absorbed this account while we waited left
        # nothing to start a group with.
        other = User.objects.filter(pk=other.pk).first()
        if other is None:
            raise FlowError("We couldn't find an account with that email address.", 404)

        shared = (
            ClusterMember.objects.filter(
                user=keeper,
                cluster__status__in=DuplicateCluster.OPEN_STATUSES,
                cluster__members__user=other,
            )
            .select_related("cluster")
            .first()
        )
        if shared is not None:
            return shared

        open_requests = DuplicateCluster.objects.filter(
            origin=DuplicateCluster.Origin.REQUESTED,
            requested_by_id=keeper.pk,
            status__in=DuplicateCluster.OPEN_STATUSES,
        ).count()
        if open_requests >= MAX_OPEN_REQUESTS:
            raise FlowError(
                f"You already have {MAX_OPEN_REQUESTS} merge requests open. "
                "Finish or cancel one first."
            )
        started = ClusterEvent.objects.filter(
            kind=ClusterEvent.Kind.REQUESTED,
            actor_id=keeper.pk,
            at__gte=now() - datetime.timedelta(days=1),
        ).count()
        if started >= MAX_REQUESTS_PER_DAY:
            raise FlowError(
                f"You've started {MAX_REQUESTS_PER_DAY} merge requests today. Try again tomorrow."
            )

        # Notified straight away: detection's email run only picks up Detected
        # groups, and this one must never get that email.
        cluster = DuplicateCluster.objects.create(
            origin=DuplicateCluster.Origin.REQUESTED,
            requested_by_id=keeper.pk,
            status=DuplicateCluster.Status.NOTIFIED,
            notified_at=now(),
        )
        mine = ClusterMember.of(cluster, keeper)
        mine.save()
        ClusterMember.of(cluster, other).save()
        log(
            cluster, ClusterEvent.Kind.REQUESTED, member=mine, actor=keeper, note=note.strip()[:500]
        )
    return mine


def request_staff(
    cluster: DuplicateCluster, keeper: User, user_id: int, note: str
) -> ServiceRequest:
    note = note.strip()
    with transaction.atomic():
        cluster = _lock(cluster, keeper.pk, user_id)
        keeper_row = require_keeper(cluster, keeper)
        row = other_row(cluster, keeper, user_id)
        if row.state == ClusterMember.State.PENDING_STAFF:
            raise FlowError("That account is already with our team")
        if not note and cluster.origin == DuplicateCluster.Origin.REQUESTED:
            raise FlowError("Tell our team a little about this account")
        request = ServiceRequest.objects.create(
            user=keeper,
            type=ServiceRequestType.REQUEST_ACCOUNT_MERGE,
            message=note or "(no note)",
        )
        player = Player.objects.filter(user=row.user).first()
        if player is not None:
            request.service_players.add(player)
        row.state = ClusterMember.State.PENDING_STAFF
        row.staff_request = request
        row.save(update_fields=["state", "staff_request"])
        log(
            cluster, ClusterEvent.Kind.STAFF_REQUESTED, member=row, actor=keeper, request=request.pk
        )
        transaction.on_commit(lambda: notify_staff_event(row, keeper_row, "requested-keeper"))
        transaction.on_commit(lambda: notify_staff_event(row, keeper_row, "requested-other"))
    return request


def _staff_row(request: ServiceRequest) -> ClusterMember:
    """The row a staff request is for, read again under _lock with its group
    and both accounts. Only inside a transaction."""
    row = ClusterMember.objects.filter(staff_request=request).select_related("cluster").first()
    if row is not None:
        cluster = _lock(row.cluster, request.user_id, row.user_id)
        row = _rows(cluster).filter(pk=row.pk, staff_request=request).first()
        request.refresh_from_db(fields=["status"])
    if (
        row is None
        or request.status != ServiceRequestStatus.PENDING
        or row.state != ClusterMember.State.PENDING_STAFF
    ):
        raise FlowError("This request is no longer waiting on a decision")
    return row


def approve_staff(request: ServiceRequest, staff: User) -> MergePlan:
    # An approval deletes an account on the strength of one person's
    # judgement, so that person must not be the one who asked.
    if request.user_id == staff.pk:
        raise FlowError(
            "You asked for this merge, so someone else on the team must approve it", 403
        )
    with transaction.atomic():
        row = _staff_row(request)
        assert row.user_id is not None  # noqa: S101 — PENDING_STAFF rows are live
        plan = merge_pair(
            row.cluster, request.user, row.user_id, actor=staff, staff_request=request
        )
        request.status = ServiceRequestStatus.APPROVED
        request.save(update_fields=["status", "updated_at"])
        log(
            row.cluster,
            ClusterEvent.Kind.STAFF_APPROVED,
            member=row,
            actor=staff,
            request=request.pk,
        )
    return plan


def reject_staff(request: ServiceRequest, staff: User) -> None:
    with transaction.atomic():
        row = _staff_row(request)
        keeper_row = membership(row.cluster, request.user)
        request.status = ServiceRequestStatus.REJECTED
        request.save(update_fields=["status", "updated_at"])
        row.state = ClusterMember.State.REJECTED
        row.staff_request = None
        row.save(update_fields=["state", "staff_request"])
        log(
            row.cluster,
            ClusterEvent.Kind.STAFF_REJECTED,
            member=row,
            actor=staff,
            request=request.pk,
        )
        if keeper_row is not None:
            notify_keeper_row = keeper_row
            transaction.on_commit(lambda: notify_staff_event(row, notify_keeper_row, "rejected"))


def merge_pair(
    cluster: DuplicateCluster,
    keeper: User,
    user_id: int,
    *,
    actor: User,
    resolved: dict[str, Any] | None = None,
    staff_request: ServiceRequest | None = None,
) -> MergePlan:
    """Fold one proven account into the keeper.

    Proven means verified for this keeper by code or inbox, or a staff
    request being approved. The server decides; the page only reflects it.
    """
    with transaction.atomic():
        cluster = _lock(cluster, keeper.pk, user_id)
        keeper_row = require_keeper(cluster, keeper, for_staff=staff_request is not None)
        row = other_row(cluster, keeper, user_id)
        if staff_request is not None:
            proof: dict[str, Any] = {
                "method": ClusterMember.Proof.STAFF,
                "by": actor.pk,
                "by_email": actor.email,
                "request": staff_request.pk,
                "at": now().isoformat(),
            }
        elif row.state == ClusterMember.State.VERIFIED and row.verified_by_id == keeper.pk:
            proof = {
                "method": row.proof,
                "by": keeper.pk,
                "at": row.verified_at.isoformat() if row.verified_at else None,
            }
        else:
            raise FlowError("Confirm this account with a code first", 403)

        absorbed = row.user
        assert absorbed is not None  # noqa: S101 — other_row only returns live rows
        # A merge does not carry is_staff over, so absorbing a staff account
        # would quietly delete it; with any weakness in the proof, anyone's.
        # Staff accounts are merged by hand with the merge_accounts command.
        if absorbed.is_staff or absorbed.is_superuser:
            raise FlowError(
                "Staff accounts can't be merged here. Our team merges them by hand", 403
            )
        absorbed_email = absorbed.email
        plan = merge_accounts(
            keeper,
            [absorbed],
            actor=actor,
            matched_by=cluster.matched_by or cluster.origin,
            resolved=resolved,
            dry_run=False,
            cluster=cluster,
            proof=proof,
        )
        close_if_done(cluster, actor)
        method = str(proof["method"])
        transaction.on_commit(lambda: notify_kept(keeper_row, absorbed_email, method))
        transaction.on_commit(
            lambda: notify_merged(
                keeper.email,
                [absorbed_email],
                PROOF_WORDS.get(method, ""),
                signs_in=method in INBOX_PROOFS,
            )
        )
    return plan
