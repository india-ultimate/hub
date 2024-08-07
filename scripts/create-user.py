#!/usr/bin/env python
"""Script to create a dev user, locally."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from server.core.models import User

DEV_EMAIL = "developer@example.com"


def create_dev_user(email: str, staff: bool, superuser: bool) -> None:
    first_name = "John"
    last_name = "Doe"
    email = email.strip().lower()
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "username": email,
            "is_staff": staff,
            "is_superuser": superuser,
        },
    )
    if not created:
        user.first_name = first_name
        user.last_name = last_name
        user.username = email
        user.is_staff = staff
        user.is_superuser = superuser

    user.set_password("password")
    user.save()

    print(f"Created user: {user}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=DEV_EMAIL)
    parser.add_argument("--not-staff", default=False, action="store_true")
    parser.add_argument("--not-superuser", default=False, action="store_true")

    args = parser.parse_args()
    create_dev_user(args.email, not args.not_staff, not args.not_superuser)
