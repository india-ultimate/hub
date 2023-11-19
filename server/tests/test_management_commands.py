from datetime import date

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils.timezone import now

from server.models import (
    Accreditation,
    Guardianship,
    ManualTransaction,
    Membership,
    Player,
    Vaccination,
)

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


class MergeUsersCommandTestCase(TestCase):
    def setUp(self) -> None:
        # Create test users and data
        self.user1 = User.objects.create(
            username="user1@example.com", email="user1@example.com", phone="1234567890"
        )
        self.user2 = User.objects.create(
            username="user2@example.com", email="user2@example.com", phone="9876543210"
        )
        self.player1 = Player.objects.create(
            user=self.user1, date_of_birth=date(2000, 1, 1), ultimate_central_id=None
        )
        self.player2 = Player.objects.create(
            user=self.user2, date_of_birth=date(1995, 5, 5), ultimate_central_id=100
        )
        self.membership1 = Membership.objects.create(
            player=self.player1,
            membership_number="M12345",
            is_annual=True,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            is_active=False,
            waiver_valid=False,
            waiver_signed_by=self.user1,
            waiver_signed_at=now(),
        )
        self.membership2 = Membership.objects.create(
            player=self.player2,
            membership_number="M67890",
            is_annual=True,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            is_active=True,
            waiver_valid=True,
            waiver_signed_by=self.user2,
            waiver_signed_at=now(),
        )
        self.guardianship = Guardianship.objects.create(
            user=self.user2, player=self.player2, relation="FA"
        )

        transaction = ManualTransaction.objects.create(user=self.user2, amount=10000)
        transaction.players.add(self.player2)

        Accreditation.objects.create(
            player=self.player2,
            is_valid=False,
            date="2023-01-01",
            level=Accreditation.AccreditationLevel.STANDARD,
            certificate="foo.pdf",
        )
        Vaccination.objects.create(
            player=self.player2,
            is_vaccinated=True,
            name=Vaccination.VaccinationName.COVAXIN,
            certificate="foo.pdf",
        )

    def test_merge_users(self) -> None:
        usernames = ["user1@example.com", "user2@example.com"]

        # Call the command
        call_command("merge_accounts", *usernames)

        # Check the database state after the merge
        user = User.objects.get()

        self.assertEqual(user.email, user.email)
        self.assertEqual(user.username, usernames[0])

        player = Player.objects.get(user=user)

        # Membership data should be merged correctly
        membership = Membership.objects.get(player=player)
        self.assertTrue(membership.is_active)
        self.assertTrue(membership.waiver_valid)

        # Guardianship should be transferred
        self.assertEqual(player.guardianship.player, player)
        self.assertEqual(player.guardianship.id, self.guardianship.id)

        # Transactions are transferred
        transaction = ManualTransaction.objects.get(user=user)
        self.assertEqual(player, transaction.players.first())

        # UC id copied
        self.assertEqual(player.ultimate_central_id, self.player2.ultimate_central_id)

        # Accreditation copied
        Accreditation.objects.get(player=player)

        # Accreditation copied
        Vaccination.objects.get(player=player)

    def tearDown(self) -> None:
        # Clean up test data
        User.objects.all().delete()
        Player.objects.all().delete()
        Membership.objects.all().delete()
        Guardianship.objects.all().delete()
