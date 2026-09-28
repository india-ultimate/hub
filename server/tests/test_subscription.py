from io import StringIO

from django.test import TestCase

from server.core.models import Player, User
from server.season.models import Season
from server.subscription.bulk_check import get_subscription_status
from server.subscription.models import Subscription


class SubscriptionStatusTestCase(TestCase):
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
        season = Season.current()
        assert season is not None  # noqa: S101 - the seeded seasons cover today

        email1 = "test1@example.com"
        user1 = User.objects.create(username=email1, email=email1)
        player1 = Player.objects.create(user=user1, date_of_birth="2001-01-01")
        Subscription.objects.create(
            is_active=True,
            player=player1,
            season=season,
            start_date=season.start_date,
            end_date=season.end_date,
        )

        email2 = "test2@example.com"
        user2 = User.objects.create(username=email2, email=email2)
        player2 = Player.objects.create(user=user2, date_of_birth="2001-01-01")
        Subscription.objects.create(
            is_active=False,
            player=player2,
            season=season,
            start_date=season.start_date,
            end_date=season.end_date,
        )
        self.email1 = email1
        self.email2 = email2

    def test_get_subscription_status_wrong_header(self) -> None:
        csv_content = StringIO(self.invalid_csv_data.strip())
        result = get_subscription_status(csv_content)
        self.assertIsNone(result)

    def test_get_subscription_status(self) -> None:
        csv_content = StringIO(self.csv_data.strip())
        result = get_subscription_status(csv_content)

        self.assertIsNotNone(result)
        # Hack for type hints, since assertIsNotNone doesn't hint the linter
        data = result if result is not None else {}

        self.assertEqual(len(data), len(self.csv_data.strip().split()) - 1)
        self.assertIn(self.email1, data)
        self.assertIn(self.email2, data)

        self.assertTrue(data[self.email1]["subscription_status"])
        self.assertFalse(data[self.email2]["subscription_status"])
