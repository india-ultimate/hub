from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from server.servicerequests.models import ServiceRequest
from server.ticket.models import Ticket
from server.transaction.models import RazorpayTransaction

rename = import_module("server.migrations.0145_subscriptions")


class TestRenameStoredValues(TestCase):
    def test_old_values_in_rows_become_subscription(self) -> None:
        from server.core.models import User

        user = User.objects.create(username="u@example.com", email="u@example.com")
        RazorpayTransaction.objects.create(
            order_id="order_old",
            amount=75000,
            currency="INR",
            user=user,
            status="created",
            type="annual-membership",
        )
        ServiceRequest.objects.create(user=user, type="REQUEST_SPONSORED_MEMBERSHIP", message="m")
        Ticket.objects.create(title="t", description="d", category="Membership", created_by=user)

        rename.rename_stored_values(apps, None)

        self.assertEqual(RazorpayTransaction.objects.get().type, "annual-subscription")
        self.assertEqual(ServiceRequest.objects.get().type, "REQUEST_SPONSORED_SUBSCRIPTION")
        self.assertEqual(Ticket.objects.get().category, "Subscription")

    def test_a_group_keeps_its_view_permission(self) -> None:
        ct = ContentType.objects.get(app_label="server", model="subscription")
        Permission.objects.filter(content_type=ct).delete()
        old = Permission.objects.create(
            content_type=ct, codename="view_membership", name="Can view membership"
        )
        staff = Group.objects.create(name="Viewers")
        staff.permissions.add(old)

        rename.rename_stored_values(apps, None)

        old.refresh_from_db()
        self.assertEqual(old.codename, "view_subscription")
        self.assertEqual(old.name, "Can view subscription")
        self.assertTrue(staff.permissions.filter(codename="view_subscription").exists())

    def test_restore_reverses_the_rename(self) -> None:
        from server.core.models import User

        user = User.objects.create(username="u2@example.com", email="u2@example.com")
        RazorpayTransaction.objects.create(
            order_id="order_old2",
            amount=75000,
            currency="INR",
            user=user,
            status="created",
            type="annual-membership",
        )
        ServiceRequest.objects.create(user=user, type="REQUEST_SPONSORED_MEMBERSHIP", message="m")
        Ticket.objects.create(title="t", description="d", category="Membership", created_by=user)
        ct = ContentType.objects.get(app_label="server", model="subscription")
        Permission.objects.filter(content_type=ct).delete()
        old = Permission.objects.create(
            content_type=ct, codename="view_membership", name="Can view membership"
        )

        rename.rename_stored_values(apps, None)
        rename.restore_stored_values(apps, None)

        self.assertEqual(RazorpayTransaction.objects.get().type, "annual-membership")
        self.assertEqual(ServiceRequest.objects.get().type, "REQUEST_SPONSORED_MEMBERSHIP")
        self.assertEqual(Ticket.objects.get().category, "Membership")
        old.refresh_from_db()
        self.assertEqual(old.codename, "view_membership")
        self.assertEqual(old.name, "Can view membership")
