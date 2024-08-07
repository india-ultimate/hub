from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from server.tournament.utils import get_bracket_match_name


def generate_pool_match_names(apps: StateApps, is_pool: bool) -> None:
    """Generate match names for pools, or position pools based on the `is_pool` flag"""
    pools = []
    if is_pool:
        Pool = apps.get_model("server", "Pool")  # noqa: N806
        pools = Pool.objects.all()
    else:
        PositionPool = apps.get_model("server", "PositionPool")  # noqa: N806
        pools = PositionPool.objects.all()

    for pool in pools:
        pool_seeding_list = sorted(map(int, pool.initial_seeding.keys()))

        for i, seed_x in enumerate(pool_seeding_list):
            for j, seed_y in enumerate(pool_seeding_list[i + 1 :], i + 1):
                pool_match_name = f"{pool.name}{i + 1} vs {pool.name}{j + 1}"

                Match = apps.get_model("server", "Match")  # noqa: N806

                pool_match = Match.objects.get(
                    tournament=pool.tournament,
                    pool=pool if is_pool else None,
                    position_pool=pool if (not is_pool) else None,
                    placeholder_seed_1=seed_x,
                    placeholder_seed_2=seed_y,
                )

                pool_match.name = pool_match_name
                pool_match.save()


def simulate_creating_bracket_sequence_matches(  # type: ignore[no-untyped-def]
    apps: StateApps,
    bracket,  # noqa: ANN001
    start: int,
    end: int,
    seq_num: int,
) -> None:
    for i in range(0, ((end - start) + 1) // 2):
        seed_1 = start + i
        seed_2 = end - i

        bracket_match_name = get_bracket_match_name(start, end, seed_1, seed_2)

        Match = apps.get_model("server", "Match")  # noqa: N806
        bracket_match = Match.objects.get(
            tournament=bracket.tournament,
            bracket=bracket,
            placeholder_seed_1=seed_1,
            placeholder_seed_2=seed_2,
        )

        bracket_match.name = bracket_match_name
        bracket_match.sequence_number = seq_num

        bracket_match.save()

    if end - start > 1:
        simulate_creating_bracket_sequence_matches(
            apps,
            bracket,
            start,
            start + (((end - start) + 1) // 2) - 1,
            seq_num + 1,
        )
        simulate_creating_bracket_sequence_matches(
            apps, bracket, start + (((end - start) + 1) // 2), end, seq_num + 1
        )


def simulate_creating_bracket_matches(  # type: ignore[no-untyped-def]
    apps: StateApps, bracket  # noqa: ANN001
) -> None:
    seeds = sorted(map(int, bracket.initial_seeding.keys()))
    start, end = seeds[0], seeds[-1]
    if ((end - start) + 1) % 2 == 0:
        simulate_creating_bracket_sequence_matches(apps, bracket, start, end, 1)


def generate_bracket_match_names(apps: StateApps) -> None:
    Bracket = apps.get_model("server", "Bracket")  # noqa: N806
    for bracket in Bracket.objects.all():
        simulate_creating_bracket_matches(apps, bracket=bracket)


def generate_cross_pool_match_names(apps: StateApps) -> None:
    Match = apps.get_model("server", "Match")  # noqa: N806
    cross_pool_matches = Match.objects.exclude(cross_pool=None)
    for cross_pool_match in cross_pool_matches:
        cross_pool_match.name = "Cross Pool"
    Match.objects.bulk_update(cross_pool_matches, ["name"])


def generate_match_names(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Generate match names for pools, position pools and brackets"""
    generate_pool_match_names(apps, is_pool=True)
    generate_pool_match_names(apps, is_pool=False)
    generate_cross_pool_match_names(apps)
    generate_bracket_match_names(apps)


def remove_match_names(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Remove match names from all matches"""
    Match = apps.get_model("server", "Match")  # noqa: N806
    matches = Match.objects.all()
    for match in matches:
        match.name = None
    Match.objects.bulk_update(matches, ["name"])


class Migration(migrations.Migration):
    dependencies = [("server", "0046_match_name")]

    operations = [migrations.RunPython(code=generate_match_names, reverse_code=remove_match_names)]
