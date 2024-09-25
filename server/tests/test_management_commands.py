import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils.timezone import now

from server.core.models import (
    Accreditation,
    Guardianship,
    Player,
    Team,
    Vaccination,
)
from server.membership.models import Membership
from server.season.models import Season
from server.series.models import Series, SeriesRegistration
from server.tournament.models import Event, Registration, Tournament
from server.transaction.models import ManualTransaction

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
            user=self.user1, date_of_birth=datetime.date(2000, 1, 1), ultimate_central_id=None
        )
        self.player2 = Player.objects.create(
            user=self.user2, date_of_birth=datetime.date(1995, 5, 5), ultimate_central_id=100
        )
        self.membership1 = Membership.objects.create(
            player=self.player1,
            membership_number="M12345",
            is_annual=True,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 12, 31),
            is_active=False,
            waiver_valid=False,
            waiver_signed_by=self.user1,
            waiver_signed_at=now(),
        )
        self.membership2 = Membership.objects.create(
            player=self.player2,
            membership_number="M67890",
            is_annual=True,
            start_date=datetime.date(2023, 1, 1),
            end_date=datetime.date(2023, 12, 31),
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


class TestImportPlayers(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "import-players.csv"
        self.cert_dir = self.fixtures_dir / "certificates"
        self.cert_dir.mkdir(exist_ok=True)
        self.cert_names = ["std.pdf", "std-2.pdf", "adv.pdf"]  # 'adv-2.pdf not created
        for name in self.cert_names:
            path = self.cert_dir / name
            with path.open("w"):
                pass

    def test_import_players(self) -> None:
        call_command("import_players", self.fixture, "--date-format", "%d-%m-%Y")

        n_players = 4
        self.assertEqual(n_players, User.objects.count())
        self.assertEqual(n_players, Player.objects.count())
        self.assertEqual(0, Guardianship.objects.count())
        self.assertEqual(n_players - 1, Accreditation.objects.count())

    def tearDown(self) -> None:
        for name in self.cert_names:
            path = self.cert_dir / name
            path.unlink(missing_ok=True)
        self.cert_dir.rmdir()


class TestActivateMemberships(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "import-players.csv"
        ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
        Season.objects.create(
            name="Season 24-25",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year+1}-07-30",
            annual_membership_amount=70000,
            sponsored_annual_membership_amount=20000,
        )

    def test_import_players(self) -> None:
        call_command("import_players", self.fixture, "--date-format", "%d-%m-%Y")
        call_command("activate_memberships", self.fixture)

        n_players = 4
        self.assertEqual(n_players, User.objects.count())
        self.assertEqual(n_players, Player.objects.count())
        self.assertEqual(n_players, Membership.objects.count())

    def tearDown(self) -> None:
        # Clean up test data
        Season.objects.all().delete()


class TestAddToSeriesRoster(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "import-players.csv"
        ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
        Season.objects.create(
            name="Season 24-25",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year+1}-07-30",
            annual_membership_amount=70000,
            sponsored_annual_membership_amount=20000,
        )
        self.series = Series.objects.create(
            name="NCS",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year}-12-30",
            type=Series.Type.MIXED,
            category=Series.Category.CLUB,
            series_roster_max_players=20,
            event_min_players_male=10,
            event_min_players_female=10,
            event_max_players_male=12,
            event_max_players_female=12,
        )
        self.team = Team.objects.create(name="Team A")

    def test_add_to_series_roster(self) -> None:
        call_command("import_players", self.fixture, "--date-format", "%d-%m-%Y")
        call_command("activate_memberships", self.fixture)
        call_command(
            "add_to_series_roster",
            self.fixture,
            "--series-id",
            self.series.id,
            "--team-id",
            self.team.id,
        )

        n_players = 4
        self.assertEqual(n_players, User.objects.count())
        self.assertEqual(n_players, Player.objects.count())
        self.assertEqual(n_players, Membership.objects.count())
        self.assertEqual(n_players, SeriesRegistration.objects.count())

    def tearDown(self) -> None:
        # Clean up test data
        Season.objects.all().delete()
        Series.objects.all().delete()
        Team.objects.all().delete()
        SeriesRegistration.objects.all().delete()


class TestAddToEventRoster(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fixtures_dir = Path(__file__).parent.joinpath("fixtures")
        self.fixture = self.fixtures_dir / "import-players.csv"
        ind_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IND")
        Season.objects.create(
            name="Season 24-25",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year+1}-07-30",
            annual_membership_amount=70000,
            sponsored_annual_membership_amount=20000,
        )
        self.series = Series.objects.create(
            name="NCS",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year}-12-30",
            type=Series.Type.MIXED,
            category=Series.Category.CLUB,
            series_roster_max_players=20,
            event_min_players_male=10,
            event_min_players_female=10,
            event_max_players_male=12,
            event_max_players_female=12,
        )
        self.team = Team.objects.create(name="Team A")
        self.event = Event.objects.create(
            title="Event",
            start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            end_date=f"{datetime.datetime.now(ind_tz).year}-12-30",
            team_registration_start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            team_registration_end_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            player_registration_start_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
            player_registration_end_date=f"{datetime.datetime.now(ind_tz).year}-08-01",
        )
        self.tournament = Tournament.objects.create(event=self.event)
        self.series.teams.add(self.team)
        self.tournament.teams.add(self.team)

    def test_add_to_event_roster(self) -> None:
        call_command("import_players", self.fixture, "--date-format", "%d-%m-%Y")
        call_command("activate_memberships", self.fixture)
        call_command(
            "add_to_series_roster",
            self.fixture,
            "--series-id",
            self.series.id,
            "--team-id",
            self.team.id,
        )
        call_command(
            "add_to_event_roster",
            self.fixture,
            "--event-id",
            self.event.id,
            "--team-id",
            self.team.id,
        )

        n_players = 4
        self.assertEqual(n_players, User.objects.count())
        self.assertEqual(n_players, Player.objects.count())
        self.assertEqual(n_players, Membership.objects.count())
        self.assertEqual(n_players, SeriesRegistration.objects.count())
        self.assertEqual(n_players, Registration.objects.count())

    def tearDown(self) -> None:
        # Clean up test data
        Season.objects.all().delete()
        Series.objects.all().delete()
        Team.objects.all().delete()
        SeriesRegistration.objects.all().delete()
        Registration.objects.all().delete()
        Event.objects.all().delete()
        Tournament.objects.all().delete()


class TestSampleData(TestCase):
    def test_import_sample_data(self) -> None:
        fixtures_dir = Path(__file__).parent.parent.joinpath("fixtures")
        fixture = fixtures_dir / "sample_data.json"
        call_command("loaddata", fixture)
