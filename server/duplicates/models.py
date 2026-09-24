"""What a merge recorded, and the groups it works from."""

import datetime
import secrets
from typing import Any

from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_prometheus.models import ExportModelOperationsMixin

from server.constants import CLAIM_TOKEN_DAYS
from server.core.models import User


class AccountMerge(ExportModelOperationsMixin("account_merge"), models.Model):  # type: ignore[misc]
    """What one merge moved, and what the deleted rows held."""

    primary_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="account_merges"
    )
    merged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merges_performed",
    )
    duplicate_user_ids = models.JSONField(default=list)
    duplicate_emails = models.JSONField(default=list)
    matched_by = models.CharField(max_length=100, blank=True)
    plan = models.JSONField(default=dict)
    # Which rows moved and which fields were overwritten, individually. A
    # count cannot be undone; this is what a reversal would be built from.
    record = models.JSONField(default=dict)
    snapshot = models.JSONField(default=list)
    # The group it came from. PROTECT: a group whose accounts were merged is
    # history, and deleting it would orphan what these rows say happened.
    cluster = models.ForeignKey(
        "DuplicateCluster", on_delete=models.PROTECT, null=True, blank=True, related_name="merges"
    )
    # The keeper as it was. primary_user is repointed if the keeper is itself
    # merged later, so these plain values are the history.
    primary_id = models.IntegerField(null=True, blank=True)
    primary_email = models.CharField(max_length=254, blank=True)
    # Who ran the merge, the same way: merged_by is repointed if they are
    # merged later. Not merged_by_id, which is merged_by's own column.
    actor_id = models.IntegerField(null=True, blank=True)
    actor_email = models.CharField(max_length=254, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class EmailAlias(ExportModelOperationsMixin("email_alias"), models.Model):  # type: ignore[misc]
    """An address absorbed by a merge, so its owner can still sign in."""

    email = models.CharField(max_length=254, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_aliases")
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def remember(cls, emails: list[str], user: User) -> list[tuple[str, int | None]]:
        """Point these addresses at user, and say what each one pointed at.

        An address can already be somebody else's alias, and repointing it
        takes away a working way for them to sign in. That is not decided
        here, but it is never allowed to happen unrecorded, so the previous
        owner is returned for the merge record.
        """
        from server.duplicates.identity import normalize_email

        # Skip only the address that already signs in by itself. Sign in
        # looks the username up exactly and an alias by its normalized form,
        # so a Gmail dot variant of the keeper's address - the same inbox,
        # a different username - needs an alias, or signing in with it makes
        # a new, empty account.
        kept = user.username
        written = []
        for email in emails:
            normalized = normalize_email(email)
            if "@" in normalized and email.strip().lower() != kept:
                held_by = (
                    cls.objects.filter(email=normalized).values_list("user_id", flat=True).first()
                )
                cls.objects.update_or_create(email=normalized, defaults={"user": user})
                written.append((normalized, held_by))
        return written


def default_claim_expiry() -> datetime.datetime:
    return now() + datetime.timedelta(days=CLAIM_TOKEN_DAYS)


class DuplicateCluster(ExportModelOperationsMixin("duplicate_cluster"), models.Model):  # type: ignore[misc]
    """Accounts believed to be one person, for that person to resolve."""

    class Status(models.TextChoices):
        DETECTED = "Detected", _("Detected")
        NOTIFIED = "Notified", _("Notified")
        RESOLVED = "Resolved", _("Resolved")
        DISMISSED = "Dismissed", _("Dismissed")

    OPEN_STATUSES = (Status.DETECTED, Status.NOTIFIED)

    class Origin(models.TextChoices):
        DETECTED = "detected", _("Found by detection")
        REQUESTED = "requested", _("Asked for by the keeper")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DETECTED)
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.DETECTED)
    # Who started a requested group, as a plain value (see ClusterEvent).
    requested_by_id = models.IntegerField(null=True, blank=True)
    matched_by = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Whose link said these are not one person. Null when nobody has.
    dismissed_by = models.ForeignKey(
        "ClusterMember", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES


class ClusterMember(ExportModelOperationsMixin("cluster_member"), models.Model):  # type: ignore[misc]
    """One account in a group: who it was, what it has proven, what happened.

    Permanent. A merge never moves or deletes one of these; it marks the row
    and clears `user`, so the group always lists every account it ever held.
    """

    class State(models.TextChoices):
        OPEN = "open", _("Not confirmed yet")
        VERIFIED = "verified", _("Confirmed")
        PENDING_STAFF = "pending-staff", _("Waiting for our team")
        REJECTED = "rejected", _("Our team couldn't confirm this one")
        MERGED = "merged", _("Merged")
        MERGED_ELSEWHERE = "merged-elsewhere", _("Merged into a different account")

    # States in which the account still exists here and could be merged.
    MERGEABLE = (State.OPEN, State.VERIFIED, State.PENDING_STAFF, State.REJECTED)

    class Proof(models.TextChoices):
        EMAIL_CODE = "email-code", _("A code sent to it")
        SAME_INBOX = "same-inbox", _("The same inbox as the keeper")
        STAFF = "staff", _("Approved by our team")

    cluster = models.ForeignKey(DuplicateCluster, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicate_memberships",
    )
    claim_token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    expires_at = models.DateTimeField(default=default_claim_expiry)
    notified_at = models.DateTimeField(null=True, blank=True)

    # The account as it was when it joined the group. Never updated.
    account_id = models.IntegerField(null=True, blank=True)
    account_email = models.CharField(max_length=254, blank=True)

    state = models.CharField(max_length=20, choices=State.choices, default=State.OPEN)
    # Plain values: a foreign key would be repointed when that account is
    # itself merged, and the history would start naming someone else.
    verified_by_id = models.IntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    proof = models.CharField(max_length=20, choices=Proof.choices, blank=True)
    merged_into_id = models.IntegerField(null=True, blank=True)
    merge = models.ForeignKey(
        AccountMerge, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    staff_request = models.ForeignKey(
        "server.ServiceRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # Only a keyed hash is kept; see server/duplicates/codes.py. When codes
    # were sent is not kept here: the limits count code-sent events across
    # every group (codes.check_budget), since a row is cheap to replace.
    code_hash = models.CharField(max_length=64, blank=True)
    code_for_id = models.IntegerField(null=True, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    code_attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ("cluster", "user")

    @classmethod
    def of(cls, cluster: DuplicateCluster, user: User) -> "ClusterMember":
        """An unsaved row for `user`, with its identity frozen as it is now."""
        return cls(cluster=cluster, user=user, account_id=user.pk, account_email=user.email)

    @property
    def is_expired(self) -> bool:
        return self.expires_at < now()

    @property
    def is_gone(self) -> bool:
        """The account was deleted outside any merge."""
        return self.user_id is None and self.state in self.MERGEABLE


class ClusterEvent(ExportModelOperationsMixin("cluster_event"), models.Model):  # type: ignore[misc]
    """Append-only timeline of a group. Written only through history.log().

    No foreign key to User on purpose: one would be repointed when that
    account is merged, and "who did this" would silently change.
    """

    class Kind(models.TextChoices):
        DETECTED = "detected"
        REQUESTED = "requested"
        EMAILED = "emailed"
        CODE_SENT = "code-sent"
        CODE_VERIFIED = "code-verified"
        CODE_FAILED = "code-failed"
        CODE_LOCKED = "code-locked"
        STAFF_REQUESTED = "staff-requested"
        STAFF_APPROVED = "staff-approved"
        STAFF_REJECTED = "staff-rejected"
        MERGED = "merged"
        MERGED_ELSEWHERE = "merged-elsewhere"
        KEEPER_MOVED = "keeper-moved"
        ACCOUNT_DELETED = "account-deleted"
        DISMISSED = "dismissed"
        CANCELLED = "cancelled"
        CLOSED = "closed"

    cluster = models.ForeignKey(DuplicateCluster, on_delete=models.PROTECT, related_name="events")
    member = models.ForeignKey(
        ClusterMember, on_delete=models.PROTECT, null=True, blank=True, related_name="events"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor_id = models.IntegerField(null=True, blank=True)
    actor_email = models.CharField(max_length=254, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["at", "id"]


@receiver(pre_delete, sender=User)
def record_deleted_account(sender: Any, instance: User, **kwargs: Any) -> None:
    """An account deleted by hand, not merged. A merge clears its rows' user
    before deleting the account, so this only sees deletions outside one."""
    from server.duplicates.history import log

    for row in ClusterMember.objects.filter(
        user=instance, state__in=ClusterMember.MERGEABLE
    ).select_related("cluster"):
        log(row.cluster, ClusterEvent.Kind.ACCOUNT_DELETED, member=row)
