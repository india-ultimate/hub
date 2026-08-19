"""Give existing tournaments the managed Format block.

Every tournament created before this carries a verbatim copy of the Format table
that shipped in `rules_default.md`, describing a 16-team event whether or not that
is what was being run. This wraps that table in the managed markers so the signals
in `server.tournament.models` can keep it accurate from here on.

Only tables still matching the shipped default are touched. Anything a person has
edited is skipped and named in the migration's output, so nobody's writing is
overwritten and you can see exactly which tournaments still need a look.
"""

from typing import Any

from django.db import migrations


def backfill_format_block(apps: Any, schema_editor: Any) -> None:
    # The concrete model, not the historical one: rendering the table needs the
    # real stage relations. Guarded below so a future schema change degrades to
    # "left the markers empty" rather than failing the whole migration.
    from server.tournament.models import Tournament as ConcreteTournament
    from server.tournament.rules import sync_rules_format, upgrade_legacy_format_block

    upgraded, skipped = [], []
    for tournament in ConcreteTournament.objects.exclude(rules__isnull=True).exclude(rules=""):
        updated = upgrade_legacy_format_block(tournament.rules)
        if updated is None:
            skipped.append(tournament)
            continue
        tournament.rules = updated
        tournament.save(update_fields=["rules"])
        try:
            sync_rules_format(tournament)
        except Exception as exc:  # — a render failure must not block the migration
            print(f"  ! could not render format for {tournament.event.title}: {exc}")
        upgraded.append(tournament)

    print(f"\n  Format block: {len(upgraded)} upgraded, {len(skipped)} left alone.")
    for tournament in skipped:
        print(f"    skipped (edited or no stock table): {tournament.event.title}")


def strip_format_block(apps: Any, schema_editor: Any) -> None:
    """Undo the wrapping, leaving the generated table as plain text."""
    from server.tournament.models import Tournament as ConcreteTournament
    from server.tournament.rules import FORMAT_BLOCK_END, FORMAT_BLOCK_START

    for tournament in ConcreteTournament.objects.exclude(rules__isnull=True).exclude(rules=""):
        rules = tournament.rules or ""
        if FORMAT_BLOCK_START not in rules:
            continue
        tournament.rules = (
            rules.replace(FORMAT_BLOCK_START + "\n", "")
            .replace("\n" + FORMAT_BLOCK_END, "")
            .replace(FORMAT_BLOCK_START, "")
            .replace(FORMAT_BLOCK_END, "")
        )
        tournament.save(update_fields=["rules"])


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0138_tournament_agent_models"),
    ]

    operations = [
        migrations.RunPython(backfill_format_block, strip_format_block),
    ]
