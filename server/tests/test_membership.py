from io import StringIO

from django.test import TestCase

from server.lib.membership import get_membership_status
from server.models import Membership, Player, User


class MembershipStatusTestCase(TestCase):
    def setUp(self) -> None:
        self.csv_data = """\
            email,field1,field2
            Test1@example.com,value1,value2
            test2@example.com,value3,value4
            test@foo.com,v1,v2
        """
        self.invalid_csv_data = """\
            email_address,field1,field2
            Test1@example.com,value1,value2
        """
        email1 = "test1@example.com"
        user1 = User.objects.create(username=email1, email=email1)
        player1 = Player.objects.create(user=user1, date_of_birth="2001-01-01")
        Membership.objects.create(
            is_active=True,
            player=player1,
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

        email2 = "test2@example.com"
        user2 = User.objects.create(username=email2, email=email2)
        player2 = Player.objects.create(user=user2, date_of_birth="2001-01-01")
        Membership.objects.create(
            is_active=False,
            player=player2,
            start_date="2023-01-01",
            end_date="2023-12-31",
        )
        self.email1 = email1
        self.email2 = email2

    def test_get_membership_status_wrong_header(self) -> None:
        csv_content = StringIO(self.invalid_csv_data.strip())
        result = get_membership_status(csv_content)
        self.assertIsNone(result)

    def test_get_membership_status(self) -> None:
        csv_content = StringIO(self.csv_data.strip())
        result = get_membership_status(csv_content)

        self.assertIsNotNone(result)
        # Hack for type hints, since assertIsNotNone doesn't hint the linter
        data = result if result is not None else {}

        self.assertEqual(len(data), len(self.csv_data.strip().split()) - 1)
        self.assertIn(self.email1, data)
        self.assertIn(self.email2, data)

        self.assertTrue(data[self.email1]["membership_status"])
        self.assertFalse(data[self.email2]["membership_status"])
