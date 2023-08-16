import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils.timezone import now

from server.models import Membership, Player, UCPerson

User = get_user_model()


class TestImportData(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        # Create a bunch of UCPerson objects to pretend data import from UC
        UCPerson.objects.create(slug="kannan")
        UCPerson.objects.create(slug="rath")
        UCPerson.objects.create(slug="ben-p-n")

    def test_import_members_data(self) -> None:
        with self.assertRaisesRegex(CommandError, "'foo' does not exist"):
            call_command("import_members_data", "foo")

        # Import Adults form data
        adults_csv = self.fixtures_dir.joinpath("form-data.csv")
        with adults_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        call_command("import_members_data", adults_csv)
        n = len(rows)
        self.assertEqual(User.objects.count(), n)
        self.assertEqual(Player.objects.count(), n)

        # Import Minors form data
        minors_csv = self.fixtures_dir.joinpath("form-data-minors.csv")
        with minors_csv.open() as f:
            reader = csv.DictReader(f)
            m_rows = list(reader)
        call_command("import_members_data", "--minors", minors_csv)
        m = len(m_rows)
        self.assertEqual(User.objects.count(), m * 2 + n)
        self.assertEqual(Player.objects.count(), m + n)


class TestInvalidateMemberships(TestCase):
    def test_invalidate_memberships(self) -> None:
        start_date = "2001-01-01"
        end_date = "2001-12-31"
        for i in range(10):
            user = User.objects.create(username=f"user-{i}")
            player = Player.objects.create(user=user, date_of_birth=start_date)
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
            self.assertIsNotNone(membership.waiver_signed_at)
            self.assertIsNotNone(membership.waiver_signed_by)
