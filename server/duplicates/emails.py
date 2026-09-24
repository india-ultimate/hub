"""The email that opens the duplicate-account flow."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from server.constants import CLAIM_TOKEN_DAYS
from server.core.models import User
from server.duplicates.codes import CODE_TTL
from server.duplicates.detect import matched_on
from server.duplicates.history import log
from server.duplicates.identity import mask_email
from server.duplicates.models import ClusterEvent, ClusterMember, DuplicateCluster
from server.task.helpers import queue_emails

SUBJECT = "You may have more than one India Ultimate Hub account"


def build_messages(cluster: DuplicateCluster) -> list[EmailMultiAlternatives]:
    """One message per account in the cluster that can actually receive it."""
    members = list(cluster.members.select_related("user").order_by("user_id"))
    base_url = settings.EMAIL_INVITATION_BASE_URL
    messages = []

    for member in members:
        if member.user is None or "@" not in member.user.email:
            continue
        context = {
            "first_name": member.user.first_name,
            "matched_on": matched_on(cluster.matched_by),
            "valid_days": CLAIM_TOKEN_DAYS,
            "claim_url": f"{base_url}/merge-accounts/{member.claim_token}",
            "accounts": [
                {
                    # Masked for everyone else: at this point the recipient is
                    # only a name and birthday match, not a proven owner.
                    "email": (
                        (
                            other.user.email
                            if other.user is not None
                            else mask_email(other.account_email)
                        )
                        if other.pk == member.pk
                        else (
                            mask_email(other.user.email)
                            if other.user is not None
                            else mask_email(other.account_email)
                        )
                    ),
                    "is_you": other.pk == member.pk,
                    # Month and year only (spec §4): a stranger from a false
                    # match should not learn the exact day, and an active
                    # membership flag is not on the table this email is
                    # allowed to show at all.
                    "last_login": other.user.last_login if other.user is not None else None,
                }
                for other in members
            ],
        }
        html = render_to_string("duplicate_accounts_email.html", context)
        message = EmailMultiAlternatives(
            subject=SUBJECT,
            body=strip_tags(html),
            from_email=settings.EMAIL_HOST_USER,
            to=[member.user.email],
        )
        message.attach_alternative(html, "text/html")
        messages.append(message)

    return messages


def notify(cluster: DuplicateCluster) -> int:
    """Queue the cluster's emails and mark it notified. 0 if there is
    nothing to send, or if the group is no longer waiting to be notified."""
    messages = build_messages(cluster)
    if not messages:
        return 0

    with transaction.atomic():
        # unnotified() reads the status outside this transaction, so two
        # workers can both hold the same group as Detected. Read it again
        # under a lock: without this both queue every address the same email
        # and both write an Emailed event.
        # no_key=True for the reason flow._lock gives at length: the events'
        # foreign key to the group is deferred and checked at COMMIT with FOR
        # KEY SHARE, which FOR UPDATE would block. A no-op on SQLite;
        # production is Postgres.
        locked = DuplicateCluster.objects.select_for_update(no_key=True).get(pk=cluster.pk)
        if locked.status != DuplicateCluster.Status.DETECTED:
            return 0
        queue_emails(messages)
        timestamp = now()
        cluster.members.filter(user__email__contains="@").update(notified_at=timestamp)
        cluster.status = DuplicateCluster.Status.NOTIFIED
        cluster.notified_at = timestamp
        cluster.save(update_fields=["status", "notified_at"])
        log(cluster, ClusterEvent.Kind.EMAILED, messages=len(messages))
    return len(messages)


def unnotified(limit: int | None = None) -> list[DuplicateCluster]:
    clusters = DuplicateCluster.objects.filter(status=DuplicateCluster.Status.DETECTED).order_by(
        "id"
    )
    return list(clusters[:limit] if limit else clusters)


MERGED_SUBJECT = "Your India Ultimate Hub account was merged"


def notify_merged(primary_email: str, absorbed: list[str], method: str = "") -> int:
    """Tell the absorbed addresses, so a merge nobody intended is visible.

    Confirming a merge only proves the person holds the account they signed
    in to, so this is how the other account's owner finds out.
    """
    html = render_to_string(
        "duplicate_accounts_merged_email.html",
        {"primary_email": mask_email(primary_email), "method": method},
    )
    messages = []
    for address in absorbed:
        if "@" not in address:
            continue
        message = EmailMultiAlternatives(
            subject=MERGED_SUBJECT,
            body=strip_tags(html),
            from_email=settings.EMAIL_HOST_USER,
            to=[address],
        )
        message.attach_alternative(html, "text/html")
        messages.append(message)

    if messages:
        queue_emails(messages)
    return len(messages)


KEPT_SUBJECT = "An account was merged into yours"

PROOF_WORDS: dict[str, str] = {
    ClusterMember.Proof.EMAIL_CODE: "confirmed by a code sent to it",
    ClusterMember.Proof.SAME_INBOX: "confirmed by your own sign in",
    ClusterMember.Proof.STAFF: "approved by our team",
}


def address(row: ClusterMember) -> str:
    """Where mail for a row goes: its account's address now. The row's
    frozen account_email is history, and the account may have moved on."""
    return row.user.email if row.user is not None else row.account_email


def notify_kept(keeper_row: ClusterMember, absorbed_email: str, method: str) -> None:
    html = render_to_string(
        "duplicate_accounts_kept_email.html",
        {
            "absorbed_email": absorbed_email,
            "method": PROOF_WORDS.get(method, method),
            "group_url": group_url(keeper_row),
        },
    )
    message = EmailMultiAlternatives(
        subject=KEPT_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[address(keeper_row)],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])


CODE_SUBJECT = "Your code to merge India Ultimate Hub accounts"


def group_url(member: ClusterMember) -> str:
    """The group's page, opened as this row. Every email ends with one."""
    return f"{settings.EMAIL_INVITATION_BASE_URL}/merge-accounts/{member.claim_token}"


def send_code_email(row: ClusterMember, keeper: User, code: str) -> None:
    """Sent now, not queued: the task queue stores bodies in the database,
    and a code must never be written anywhere."""
    html = render_to_string(
        "duplicate_accounts_code_email.html",
        {
            "code": code,
            "keeper_email": mask_email(keeper.email),
            "minutes": int(CODE_TTL.total_seconds() // 60),
            "row_url": group_url(row),
        },
    )
    message = EmailMultiAlternatives(
        subject=CODE_SUBJECT,
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[address(row)],
    )
    message.attach_alternative(html, "text/html")
    message.send()


STAFF_SUBJECTS = {
    "requested-keeper": "We're reviewing your merge request",
    "requested-other": "Someone asked to merge your India Ultimate Hub account",
    "rejected": "We couldn't confirm an account for your merge",
}


def notify_staff_event(row: ClusterMember, keeper_row: ClusterMember, kind: str) -> None:
    """kind: requested-keeper, requested-other or rejected. The other
    account's own link goes to the other address, so its owner can object.

    The other address is masked whichever group this is. The page opens up
    a detected group's addresses to its members (spec §4), but a requested
    group's was typed, and a typed address can be an alias — then the
    account's own address is one the keeper never typed, and the page masks
    it there too.
    """
    to_row = row if kind == "requested-other" else keeper_row
    html = render_to_string(
        "duplicate_accounts_staff_email.html",
        {
            "kind": kind,
            "keeper_email": mask_email(address(keeper_row)),
            "other_email": mask_email(row.account_email),
            "group_url": group_url(to_row),
        },
    )
    message = EmailMultiAlternatives(
        subject=STAFF_SUBJECTS[kind],
        body=strip_tags(html),
        from_email=settings.EMAIL_HOST_USER,
        to=[address(to_row)],
    )
    message.attach_alternative(html, "text/html")
    queue_emails([message])
