import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from server.models import Player

User = get_user_model()


class TestImportData(TestCase):
    def setUp(self):
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")

    def test_import_data(self) -> None:
        with self.assertRaisesRegex(CommandError, "'foo' does not exist"):
            call_command("import_data", "foo")

        # Import Adults form data
        adults_csv = self.fixtures_dir.joinpath("form-data.csv")
        with adults_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        call_command("import_data", adults_csv)
        n = len(rows)
        self.assertEqual(User.objects.count(), n)
        self.assertEqual(Player.objects.count(), n)

        # Import Minors form data
        minors_csv = self.fixtures_dir.joinpath("form-data-minors.csv")
        with minors_csv.open() as f:
            reader = csv.DictReader(f)
            m_rows = list(reader)
        call_command("import_data", "--minors", minors_csv)
        m = len(m_rows)
        self.assertEqual(User.objects.count(), m * 2 + n)
        self.assertEqual(Player.objects.count(), m + n)
