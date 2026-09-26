"""Give every membership a season and, where the payment says so, a tier."""

import datetime
from typing import Any

import django.db.models.deletion
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

# What each season charged before this change, so a historical payment can be
# read back to the tier it bought. The amounts within a season are distinct.
OLD_PRICES: dict[str, dict[int, str]] = {
    "Season 2024-2025": {70000: "regular", 20000: "discounted"},
    "Season 2025-2026": {150000: "patron", 75000: "regular", 25000: "discounted"},
    # 25000 was still Discounted's price under this pre-2026 list -- the new
    # catalog's Community tier (also priced at 25000, seeded by 0147) didn't
    # exist yet when these historical payments were made. Don't "fix" this
    # to community.
    "Season 2026-2027": {150000: "patron", 75000: "regular", 25000: "discounted"},
}

# A payment made before `start_date`/`end_date` were reliably recorded on the
# transaction (RazorpayTransaction defaults both to this).
UNSET_DATE = datetime.date(1900, 1, 1)


def season_for(season_model: Any, day: Any) -> Any:
    return season_model.objects.filter(start_date__lte=day, end_date__gte=day).first()


def bucket_unseasoned(apps: Any, schema_editor: Any) -> None:
    """Step 2: every row with no season gets the one containing its start."""
    Membership = apps.get_model("server", "Membership")  # noqa: N806
    Season = apps.get_model("server", "Season")  # noqa: N806
    for membership in Membership.objects.filter(season__isnull=True):
        season = season_for(Season, membership.start_date)
        if season is not None:
            membership.season = season
            membership.save(update_fields=["season"])


def _per_player_amount(transaction: Any) -> tuple[int | None, int]:
    """The amount per player in one order, and how many players it covers."""
    count = transaction.players.count()
    each = transaction.amount // count if count else None
    return each, count


def _tier_for_amount(prices: dict[int, str], each: int | None, player_count: int) -> str | None:
    """The tier a per-player amount bought, or None if a group order makes it ambiguous.

    A single-player order's price maps to its tier directly. A group order
    can only average to exactly a season's lowest or highest price if every
    member paid that same price -- any other value the season sells at,
    including one a mix of tiers happens to average out to (patron:discounted
    2:3 in a 150000/75000/25000 season averages to exactly 75000, "regular"'s
    own price), can't be told apart from a genuine mix, so it is left
    unresolved rather than guessed.
    """
    if each is None:
        return None
    slug = prices.get(each)
    if slug is None or player_count <= 1:
        return slug
    return slug if each in (min(prices), max(prices)) else None


def reconstruct_tiers(apps: Any, schema_editor: Any) -> None:
    """Step 5: read each membership's tier back from what was paid for it."""
    Membership = apps.get_model("server", "Membership")  # noqa: N806
    MembershipPlan = apps.get_model("server", "MembershipPlan")  # noqa: N806
    RazorpayTransaction = apps.get_model("server", "RazorpayTransaction")  # noqa: N806

    plans = {
        (plan.season.name, plan.type.slug): plan
        for plan in MembershipPlan.objects.select_related("season", "type")
    }

    for membership in Membership.objects.select_related("season").filter(
        season__isnull=False, plan__isnull=True
    ):
        prices = OLD_PRICES.get(membership.season.name)
        if not prices:
            continue
        # The most recent completed payment decides the tier, in case of a
        # repurchase or an amendment.
        paid = (
            RazorpayTransaction.objects.filter(
                players=membership.player_id,
                season=membership.season_id,
                status="completed",
                type="annual-membership",
            )
            .order_by("payment_date")
            .last()
        )
        if paid is None:
            continue
        each, count = _per_player_amount(paid)
        slug = _tier_for_amount(prices, each, count)
        # What was paid is kept even when the tier can't be resolved, as
        # recover_overwritten does: a live row with no amount would be quoted
        # a full-price "upgrade" to the tier it may already hold.
        membership.plan = plans.get((membership.season.name, slug)) if slug else None
        membership.amount_paid = each
        membership.save(update_fields=["plan", "amount_paid"])


def recover_overwritten(apps: Any, schema_editor: Any) -> None:
    """Step 6: rebuild memberships that later purchases overwrote.

    The row is gone, but the payment that bought it is not. These come back
    inactive: they are history, not a live membership.
    """
    Membership = apps.get_model("server", "Membership")  # noqa: N806
    MembershipPlan = apps.get_model("server", "MembershipPlan")  # noqa: N806
    RazorpayTransaction = apps.get_model("server", "RazorpayTransaction")  # noqa: N806

    plans = {
        (plan.season.name, plan.type.slug): plan
        for plan in MembershipPlan.objects.select_related("season", "type")
    }
    held = set(Membership.objects.values_list("player_id", "season_id"))

    for paid in RazorpayTransaction.objects.filter(
        status="completed", type="annual-membership", season__isnull=False
    ).select_related("season"):
        each, count = _per_player_amount(paid)
        prices = OLD_PRICES.get(paid.season.name, {})
        slug = _tier_for_amount(prices, each, count)
        plan = plans.get((paid.season.name, slug)) if slug else None
        start_date = paid.start_date if paid.start_date != UNSET_DATE else paid.season.start_date
        end_date = paid.end_date if paid.end_date != UNSET_DATE else paid.season.end_date
        for player_id in paid.players.values_list("id", flat=True):
            if (player_id, paid.season_id) in held:
                continue
            Membership.objects.create(
                player_id=player_id,
                season=paid.season,
                plan=plan,
                # Kept even when the tier couldn't be resolved: staff
                # reviewing an unresolved row still want to see what was paid.
                amount_paid=each,
                start_date=start_date,
                end_date=end_date,
                is_active=False,
                waiver_valid=False,
            )
            held.add((player_id, paid.season_id))


def assign_numbers(apps: Any, schema_editor: Any) -> None:
    """Step 7: renumber everyone who holds a membership, oldest first."""
    Membership = apps.get_model("server", "Membership")  # noqa: N806
    Player = apps.get_model("server", "Player")  # noqa: N806

    first_by_player: dict[int, tuple[Any, Any]] = {}
    for membership in Membership.objects.select_related("season").order_by(
        "season__start_date", "start_date", "player_id"
    ):
        if membership.season is None:
            raise RuntimeError(
                f"Membership {membership.pk} (start {membership.start_date}) has no season: "
                "no season covers its start date. Add one before migrating."
            )
        first_by_player.setdefault(membership.player_id, (membership.season, membership.start_date))

    by_season: dict[int, list[tuple[Any, int]]] = {}
    for player_id, (season, start) in first_by_player.items():
        by_season.setdefault(season.start_date.year % 100, []).append((start, player_id))

    for code, entries in by_season.items():
        entries.sort()
        for position, (_start, player_id) in enumerate(entries, start=1):
            Player.objects.filter(pk=player_id).update(
                membership_number=f"IU-{code:02d}-{position:04d}"
            )


def check_constraints_now(apps: Any, schema_editor: Any) -> None:
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def irreversible(apps: Any, schema_editor: Any) -> None:
    raise IrreversibleError(
        "Recovered history can't be un-recovered: once a player holds more "
        "than one season's membership, there is no single prior row to "
        "revert to."
    )


class Migration(migrations.Migration):
    dependencies = [("server", "0148_membership_per_season")]

    operations = [
        # `player` drops the old OneToOneField's implicit unique-per-player
        # constraint before recover_overwritten below tries to give a player
        # a second row for an earlier season -- every overwritten purchase
        # this task recovers needs exactly that. This is purely a loosening
        # (ForeignKey admits everything OneToOneField did), so it is safe to
        # run before the data is cleaned up.
        migrations.AlterField(
            model_name="membership",
            name="player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="memberships",
                to="server.player",
            ),
        ),
        migrations.RunPython(bucket_unseasoned, irreversible),
        migrations.RunPython(reconstruct_tiers, irreversible),
        migrations.RunPython(recover_overwritten, irreversible),
        migrations.RunPython(assign_numbers, irreversible),
        # The steps above write rows whose foreign keys Postgres checks at
        # commit, and it refuses to ALTER a table with such checks pending
        # ("pending trigger events"). Run them now. SQLite has no such
        # statement and no such problem.
        migrations.RunPython(check_constraints_now, migrations.RunPython.noop),
        # Only now is it safe: every row has a season and no player holds two
        # rows for one season.
        migrations.AlterField(
            model_name="membership",
            name="season",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="server.season",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="membership",
            unique_together={("player", "season")},
        ),
    ]
