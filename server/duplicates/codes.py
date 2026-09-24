"""Proving control of an inbox with a code emailed to it.

Deliberately separate from sign-in OTPs, which are checked against a
timestamp the client supplies and so never expire.
"""

import datetime
import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils.timezone import now

from server.core.models import User
from server.duplicates.models import ClusterEvent, ClusterMember

CODE_DIGITS = 6
CODE_TTL = datetime.timedelta(minutes=10)
RESEND_AFTER = datetime.timedelta(minutes=1)
MAX_ATTEMPTS = 5
# A new code resets the attempts, so without a daily cap a resend a minute is
# 7,200 guesses a day at a million codes. Five codes is 25 guesses, per
# account, whichever group or person asks.
MAX_CODES_PER_DAY = 5
# Codes one person can ask for in a day, across every account. Someone
# merging their own old accounts sends a handful; this is for someone
# working through other people's.
MAX_CODES_PER_ACTOR_PER_DAY = 15


class CodeError(Exception):
    """Why a code was refused, in words the page can show."""

    def __init__(self, message: str, *, locked: bool = False) -> None:
        super().__init__(message)
        self.locked = locked


def check_budget(account_id: int, keeper: User) -> None:
    """Refuse a code the day's limits do not allow.

    Counted from the code-sent events of every group, not from one group
    row: a row is cheap to replace, since cancelling a request and asking
    again makes a new one, and a count kept on the row starts again with it.
    The caller holds a lock on both accounts, so two sends cannot both count
    the same events and both pass.
    """
    sent = ClusterEvent.objects.filter(
        kind=ClusterEvent.Kind.CODE_SENT, at__gte=now() - datetime.timedelta(days=1)
    )
    to_account = sent.filter(member__account_id=account_id)
    last = to_account.aggregate(last=Max("at"))["last"]
    if last is not None and now() - last < RESEND_AFTER:
        raise CodeError("Wait a minute before asking for another code")
    if to_account.count() >= MAX_CODES_PER_DAY:
        raise CodeError("Too many codes today for this account. Try again tomorrow")
    if sent.filter(actor_id=keeper.pk).count() >= MAX_CODES_PER_ACTOR_PER_DAY:
        raise CodeError("You've asked for too many codes today. Try again tomorrow")


def _digest(member: ClusterMember, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{member.pk}:{code}".encode(), hashlib.sha256).hexdigest()


def issue(member: ClusterMember, keeper: User) -> str:
    """A fresh code for `keeper` to prove `member`'s inbox. Returns the code;
    the caller emails it and must not store it anywhere. How many codes may
    be sent is check_budget's question, not this row's."""
    with transaction.atomic():
        # Locked so two near-simultaneous calls cannot interleave their
        # writes to the code. A no-op on SQLite, which is why no test can
        # prove it works; the test suite is SQLite and production is
        # Postgres.
        row = ClusterMember.objects.select_for_update().get(pk=member.pk)
        code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
        row.code_hash = _digest(row, code)
        row.code_for_id = keeper.pk
        row.code_expires_at = now() + CODE_TTL
        row.code_attempts = 0
        row.save(
            update_fields=[
                "code_hash",
                "code_for_id",
                "code_expires_at",
                "code_attempts",
            ]
        )
    member.code_hash = row.code_hash
    member.code_for_id = row.code_for_id
    member.code_expires_at = row.code_expires_at
    member.code_attempts = row.code_attempts
    return code


def check(member: ClusterMember, keeper: User, code: str) -> CodeError | None:
    """Accept, or say why not. A correct code works once.

    The refusal is returned, not raised: the caller writes its event in the
    same transaction as the attempt it counts, and an exception raised
    there would roll back the attempt it reports.
    """
    error: CodeError | None
    with transaction.atomic():
        # Locked for the whole check: the attempt counter is what bounds
        # guessing, and a read-modify-write on it without a lock lets
        # concurrent wrong guesses each read the same stale count and each
        # write back the same +1 - a lost update that turns a 5-attempt
        # lock into no lock at all. A no-op on SQLite, which is why no test
        # can prove it works; the test suite is SQLite and production is
        # Postgres.
        row = ClusterMember.objects.select_for_update().get(pk=member.pk)
        if not row.code_hash or row.code_for_id != keeper.pk:
            error = CodeError("Ask for a code first")
        elif row.code_attempts >= MAX_ATTEMPTS:
            error = CodeError("Too many wrong codes. Ask for a new one", locked=True)
        elif row.code_expires_at is None or row.code_expires_at < now():
            error = CodeError("That code has expired. Ask for a new one")
        else:
            typed = "".join(code.split())
            if not hmac.compare_digest(row.code_hash, _digest(row, typed)):
                row.code_attempts += 1
                row.save(update_fields=["code_attempts"])
                error = CodeError("That code isn't right", locked=row.code_attempts >= MAX_ATTEMPTS)
            else:
                row.code_hash = ""
                row.code_for_id = None
                row.code_expires_at = None
                row.save(update_fields=["code_hash", "code_for_id", "code_expires_at"])
                error = None
    member.code_hash = row.code_hash
    member.code_for_id = row.code_for_id
    member.code_expires_at = row.code_expires_at
    member.code_attempts = row.code_attempts
    return error
