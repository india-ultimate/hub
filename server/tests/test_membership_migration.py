import datetime
import importlib
from typing import Any
from unittest import mock

from django.apps import apps
from django.db.migrations.exceptions import IrreversibleError
from django.test import TestCase

from server.membership.models import Membership
from server.season.models import Season
from server.transaction.models import RazorpayTransaction

from .test_membership_model import make_player

migration = importlib.import_module("server.migrations.0149_membership_history")


def make_transaction(
    *,
    order_id: str,
    season: Season,
    players: list[Any],
    amount: int,
    status: str = "completed",
    start_date: datetime.date | None = None,
    end_date: datetime.date | None = None,
) -> RazorpayTransaction:
    kwargs: dict[str, Any] = {}
    if start_date is not None:
        kwargs["start_date"] = start_date
    if end_date is not None:
        kwargs["end_date"] = end_date
    txn = RazorpayTransaction.objects.create(
        order_id=order_id,
        payment_id=f"pay-{order_id}",
        payment_signature=f"sig-{order_id}",
        amount=amount,
        currency="INR",
        status=status,
        type="annual-membership",
        user=players[0].user,
        season=season,
        **kwargs,
    )
    for player in players:
        txn.players.add(player)
    return txn


class TestBucketingByDate(TestCase):
    """Every legacy row must land in the season containing its start date."""

    def test_the_five_production_date_windows_all_find_a_season(self) -> None:
        windows = [
            ("2022-04-01", "2023-03-31", "Season 2022-2023"),
            ("2023-06-01", "2024-05-31", "Season 2023-2024"),
            ("2024-03-23", "2024-03-24", "Season 2023-2024"),
            ("2024-04-13", "2024-04-14", "Season 2023-2024"),
            ("2024-06-01", "2025-05-31", "Season 2023-2024"),
        ]
        for start, _end, expected in windows:
            season = Season.containing(datetime.date.fromisoformat(start))
            assert season is not None, f"no season contains {start}"  # noqa: S101
            self.assertEqual(season.name, expected, start)


class TestMigratedShape(TestCase):
    def test_a_player_may_now_hold_several_seasons(self) -> None:
        player = make_player("h@example.com")
        s25 = Season.objects.get(name="Season 2025-2026")
        s26 = Season.objects.get(name="Season 2026-2027")
        Membership.objects.create(
            player=player, season=s25, start_date=s25.start_date, end_date=s25.end_date
        )
        Membership.objects.create(
            player=player, season=s26, start_date=s26.start_date, end_date=s26.end_date
        )
        self.assertEqual(player.memberships.count(), 2)


class TestBucketUnseasoned(TestCase):
    """`season` is non-null in the live schema, so a genuine no-season row
    can no longer be created here -- a double stands in for one so the
    function's own logic (find it, look up its season, save it) still runs
    for real, against the real, seeded Season rows.
    """

    def test_assigns_the_season_containing_the_start_date(self) -> None:
        membership = mock.Mock(season=None, start_date=datetime.date(2024, 3, 23))
        manager = mock.Mock()
        manager.filter.return_value = [membership]

        def get_model(app_label: str, name: str) -> Any:
            if name == "Membership":
                return mock.Mock(objects=manager)
            if name == "Season":
                return Season
            raise AssertionError(name)

        historical_apps = mock.Mock()
        historical_apps.get_model.side_effect = get_model

        migration.bucket_unseasoned(historical_apps, None)

        manager.filter.assert_called_once_with(season__isnull=True)
        self.assertEqual(membership.season, Season.objects.get(name="Season 2023-2024"))
        membership.save.assert_called_once_with(update_fields=["season"])

    def test_leaves_a_date_outside_every_season_alone(self) -> None:
        membership = mock.Mock(season=None, start_date=datetime.date(1999, 1, 1))
        manager = mock.Mock()
        manager.filter.return_value = [membership]

        def get_model(app_label: str, name: str) -> Any:
            return mock.Mock(objects=manager) if name == "Membership" else Season

        historical_apps = mock.Mock()
        historical_apps.get_model.side_effect = get_model

        migration.bucket_unseasoned(historical_apps, None)

        membership.save.assert_not_called()


class TestReconstructTiers(TestCase):
    """Fills in the tier on rows that already exist but have none, from
    whatever completed payment named that player and season.
    """

    def setUp(self) -> None:
        self.s2526 = Season.objects.get(name="Season 2025-2026")
        self.s2223 = Season.objects.get(name="Season 2022-2023")

    def _existing_row(self, email: str, season: Season) -> Any:
        player = make_player(email)
        Membership.objects.create(
            player=player, season=season, start_date=season.start_date, end_date=season.end_date
        )
        return player

    def test_a_single_player_order_resolves_at_each_price(self) -> None:
        patron = self._existing_row("patron@example.com", self.s2526)
        regular = self._existing_row("regular@example.com", self.s2526)
        discounted = self._existing_row("discounted@example.com", self.s2526)
        make_transaction(order_id="o-patron", season=self.s2526, players=[patron], amount=150000)
        make_transaction(order_id="o-regular", season=self.s2526, players=[regular], amount=75000)
        make_transaction(
            order_id="o-discounted", season=self.s2526, players=[discounted], amount=25000
        )

        migration.reconstruct_tiers(apps, None)

        cases = [
            (patron, "patron", 150000),
            (regular, "regular", 75000),
            (discounted, "discounted", 25000),
        ]
        for player, slug, amount in cases:
            membership = Membership.objects.get(player=player, season=self.s2526)
            assert membership.plan is not None  # noqa: S101
            self.assertEqual(membership.plan.type.slug, slug)
            self.assertEqual(membership.amount_paid, amount)

    def test_a_mixed_tier_group_order_is_left_unresolved(self) -> None:
        # 2 patron (150000) + 3 discounted (25000) averages to exactly
        # 75000 -- "regular"'s own price -- but is not one.
        players = [self._existing_row(f"mix{i}@example.com", self.s2526) for i in range(5)]
        make_transaction(
            order_id="o-mixed", season=self.s2526, players=players, amount=2 * 150000 + 3 * 25000
        )

        migration.reconstruct_tiers(apps, None)

        for player in players:
            membership = Membership.objects.get(player=player, season=self.s2526)
            self.assertIsNone(membership.plan)
            # What they paid is still known, so no later quote treats it as nothing.
            self.assertEqual(membership.amount_paid, 75000)

    def test_a_never_paid_row_is_left_alone(self) -> None:
        player = self._existing_row("neverpaid@example.com", self.s2526)

        migration.reconstruct_tiers(apps, None)

        membership = Membership.objects.get(player=player, season=self.s2526)
        self.assertIsNone(membership.plan)

    def test_a_legacy_pre_catalog_season_never_gets_a_tier(self) -> None:
        player = self._existing_row("legacy@example.com", self.s2223)
        make_transaction(order_id="o-legacy", season=self.s2223, players=[player], amount=50000)

        migration.reconstruct_tiers(apps, None)

        membership = Membership.objects.get(player=player, season=self.s2223)
        self.assertIsNone(membership.plan)

    def test_never_creates_or_deletes_a_row(self) -> None:
        self._existing_row("count-a@example.com", self.s2526)
        self._existing_row("count-b@example.com", self.s2223)
        before = Membership.objects.count()

        migration.reconstruct_tiers(apps, None)

        self.assertEqual(Membership.objects.count(), before)


class TestRecoverOverwritten(TestCase):
    """Rebuilds the row a later purchase overwrote, from a still-complete
    payment naming a (player, season) nobody currently holds a row for.
    """

    def setUp(self) -> None:
        self.s2526 = Season.objects.get(name="Season 2025-2026")
        self.s2223 = Season.objects.get(name="Season 2022-2023")

    def test_recovers_a_single_player_order(self) -> None:
        player = make_player("recover@example.com")
        make_transaction(order_id="o-recover", season=self.s2526, players=[player], amount=25000)

        migration.recover_overwritten(apps, None)

        membership = Membership.objects.get(player=player, season=self.s2526)
        assert membership.plan is not None  # noqa: S101
        self.assertEqual(membership.plan.type.slug, "discounted")
        self.assertEqual(membership.amount_paid, 25000)
        self.assertFalse(membership.is_active)

    def test_a_mixed_tier_group_order_is_recovered_with_no_tier(self) -> None:
        players = [make_player(f"newmix{i}@example.com") for i in range(5)]
        make_transaction(
            order_id="o-newmixed",
            season=self.s2526,
            players=players,
            amount=2 * 150000 + 3 * 25000,
        )

        migration.recover_overwritten(apps, None)

        for player in players:
            membership = Membership.objects.get(player=player, season=self.s2526)
            self.assertIsNone(membership.plan)
            # Kept even though the tier is unresolved, for staff to review.
            self.assertEqual(membership.amount_paid, 75000)

    def test_a_double_payment_for_one_season_recovers_only_one_row(self) -> None:
        player = make_player("double@example.com")
        make_transaction(order_id="o-double-1", season=self.s2526, players=[player], amount=75000)
        make_transaction(order_id="o-double-2", season=self.s2526, players=[player], amount=75000)

        migration.recover_overwritten(apps, None)

        self.assertEqual(Membership.objects.filter(player=player, season=self.s2526).count(), 1)

    def test_a_pending_only_payment_recovers_nothing(self) -> None:
        player = make_player("pending@example.com")
        make_transaction(
            order_id="o-pending",
            season=self.s2526,
            players=[player],
            amount=75000,
            status="pending",
        )

        migration.recover_overwritten(apps, None)

        self.assertEqual(Membership.objects.filter(player=player).count(), 0)

    def test_a_legacy_season_is_recovered_with_no_tier_and_the_seasons_dates(self) -> None:
        player = make_player("legacyrecover@example.com")
        # Leave start_date/end_date unset -- RazorpayTransaction's own
        # 1900-01-01 default -- so the season's dates must be used instead.
        make_transaction(
            order_id="o-legacyrecover", season=self.s2223, players=[player], amount=50000
        )

        migration.recover_overwritten(apps, None)

        membership = Membership.objects.get(player=player, season=self.s2223)
        self.assertIsNone(membership.plan)
        self.assertEqual(membership.amount_paid, 50000)
        self.assertEqual(membership.start_date, self.s2223.start_date)
        self.assertEqual(membership.end_date, self.s2223.end_date)

    def test_every_player_season_pair_stays_unique(self) -> None:
        held_player = make_player("held@example.com")
        Membership.objects.create(
            player=held_player,
            season=self.s2526,
            start_date=self.s2526.start_date,
            end_date=self.s2526.end_date,
        )
        make_transaction(order_id="o-held", season=self.s2526, players=[held_player], amount=75000)
        fresh_player = make_player("fresh@example.com")
        make_transaction(
            order_id="o-fresh", season=self.s2526, players=[fresh_player], amount=25000
        )

        migration.recover_overwritten(apps, None)

        pairs = list(Membership.objects.values_list("player_id", "season_id"))
        self.assertEqual(len(pairs), len(set(pairs)))
        # The already-held row wasn't touched or duplicated.
        self.assertEqual(Membership.objects.filter(player=held_player).count(), 1)


class TestAssignNumbers(TestCase):
    """Numbers everyone who holds a membership, by the season and date they
    first held one -- regardless of how many seasons they hold now.
    """

    def test_the_iu_yy_nnnn_order(self) -> None:
        s2425 = Season.objects.get(name="Season 2024-2025")
        s2526 = Season.objects.get(name="Season 2025-2026")

        x = make_player("x@example.com")
        w = make_player("w@example.com")
        y = make_player("y@example.com")
        z = make_player("z@example.com")

        Membership.objects.create(
            player=x, season=s2425, start_date=s2425.start_date, end_date=s2425.end_date
        )
        # W's first season is also 2024-25, but a later start_date within it
        # -- second place in that season, and never counted again for 2025-26.
        Membership.objects.create(
            player=w,
            season=s2425,
            start_date=s2425.start_date + datetime.timedelta(days=5),
            end_date=s2425.end_date,
        )
        Membership.objects.create(
            player=w, season=s2526, start_date=s2526.start_date, end_date=s2526.end_date
        )
        Membership.objects.create(
            player=y, season=s2526, start_date=s2526.start_date, end_date=s2526.end_date
        )
        Membership.objects.create(
            player=z,
            season=s2526,
            start_date=s2526.start_date + datetime.timedelta(days=10),
            end_date=s2526.end_date,
        )

        migration.assign_numbers(apps, None)

        for player, expected in [
            (x, "IU-24-0001"),
            (w, "IU-24-0002"),
            (y, "IU-25-0001"),
            (z, "IU-25-0002"),
        ]:
            player.refresh_from_db()
            self.assertEqual(player.membership_number, expected)

    def test_a_row_with_no_season_fails_naming_it(self) -> None:
        row = mock.Mock(pk=7, season=None, start_date=datetime.date(2021, 1, 1), player_id=1)
        fake_apps = mock.Mock()
        query = fake_apps.get_model.return_value.objects.select_related.return_value
        query.order_by.return_value = [row]

        with self.assertRaisesRegex(RuntimeError, "Membership 7 \\(start 2021-01-01\\)"):
            migration.assign_numbers(fake_apps, None)


class TestIrreversible(TestCase):
    def test_the_data_steps_refuse_to_reverse(self) -> None:
        with self.assertRaises(IrreversibleError):
            migration.irreversible(apps, None)
