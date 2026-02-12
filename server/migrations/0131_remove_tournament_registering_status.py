from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def migrate_registering_to_scheduling(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Convert any tournaments with REGISTERING (REG) status to SCHEDULING (SCH)."""
    tournament_model = apps.get_model("server", "Tournament")
    tournament_model.objects.filter(status="REG").update(status="SCH")


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0130_backfill_late_penalty_end_dates"),
    ]

    operations = [
        migrations.RunPython(
            migrate_registering_to_scheduling,
            migrations.RunPython.noop,
        ),
    ]
