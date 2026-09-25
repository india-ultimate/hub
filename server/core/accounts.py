"""Resolving which account an email address signs in to."""

from typing import Any

from django.db import IntegrityError, transaction

from server.core.models import User
from server.duplicates.identity import normalize_email
from server.duplicates.models import AccountMerge, EmailAlias


def find_user(user_id: int) -> User | None:
    """The account an id signs in to: itself, or the one a merge folded it into."""
    if user := User.objects.filter(id=user_id).first():
        return user
    # primary_user is repointed when a keeper is merged later, so it is the survivor.
    merges = AccountMerge.objects.select_related("primary_user").iterator()
    return next((m.primary_user for m in merges if user_id in m.duplicate_user_ids), None)


def find_login_user(email: str) -> User | None:
    """The account an address signs in to, without creating one: the
    username, then an address a merge absorbed."""
    address = email.strip().lower()
    match = User.objects.filter(username=address).first()
    if match is not None:
        return match
    alias = EmailAlias.objects.filter(email=normalize_email(address)).select_related("user").first()
    return alias.user if alias is not None else None


def resolve_login_user(email: str, **defaults: Any) -> User:
    """Find the account an address signs in to, creating one if absent, with
    `defaults` for the new account's other fields.

    Every path that makes an account for an address comes through here, so
    an address a merge absorbed finds the account that absorbed it. A new
    account made for it would capture its sign in from then on.

    username is the address: every path that makes an account sets it from
    the email, and nothing edits an email afterwards. It is also unique, so
    this is a single lookup on an existing index with exactly one answer.

    The previous version matched username and email together, which missed
    any account whose username is a name slug and silently created a second
    account for it on every sign in.
    """
    found = find_login_user(email)
    if found is not None:
        return found
    address = email.strip().lower()
    try:
        # Inside its own savepoint: a loser here has to leave the caller's
        # transaction usable, since this runs mid-request.
        with transaction.atomic():
            return User.objects.create(username=address, email=address, **defaults)
    except IntegrityError:
        # Two requests for an address neither of them found can both get
        # here; the unique username lets exactly one insert through. The
        # loser wants the winner's account, not an error - that is what the
        # get_or_create this replaced did, and the lookup above is why it
        # cannot simply come back.
        raced = find_login_user(email)
        if raced is None:
            raise
        return raced
