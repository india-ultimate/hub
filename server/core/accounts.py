"""Resolving which account an email address signs in to."""

from typing import Any

from server.core.models import User


def find_login_user(email: str) -> User | None:
    """The account an address signs in to, without creating one."""
    address = email.strip().lower()
    return User.objects.filter(username=address).first()


def resolve_login_user(email: str, **defaults: Any) -> User:
    """Find the account an address signs in to, creating one if absent, with
    `defaults` for the new account's other fields.

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
    return User.objects.create(username=address, email=address, **defaults)
