from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils.timezone import now

from server.models import Membership, Player

User = get_user_model()


class TestInvalidateMemberships(TestCase):
    def test_invalidate_memberships(self) -> None:
        start_date = "2001-01-01"
        end_date = "2001-12-31"
        for i in range(10):
            user = User.objects.create(username=f"user-{i}")
            player = Player.objects.create(
                user=user, date_of_birth=start_date, sponsored=i % 2 == 0
            )
            Membership.objects.create(
                player=player,
                start_date=start_date,
                end_date=end_date,
                is_active=True,
                waiver_signed_by=user,
                waiver_signed_at=now(),
                waiver_valid=True,
            )
        call_command("invalidate_memberships")
        for membership in Membership.objects.filter():
            self.assertFalse(membership.is_active)
            self.assertFalse(membership.waiver_valid)
            self.assertFalse(membership.player.sponsored)
            self.assertIsNotNone(membership.waiver_signed_at)
            self.assertIsNotNone(membership.waiver_signed_by)
