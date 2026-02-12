# Backfill ticket status: set Closed (CLS) to Resolved (RES).

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_closed_to_resolved(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Set status to Resolved for tickets currently Closed."""
    Ticket = apps.get_model("server", "Ticket")  # noqa: N806
    Ticket.objects.filter(status="CLS").update(status="RES")


def reverse_backfill(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """No-op: we cannot reliably restore which tickets were Closed."""


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0126_backfill_ticket_category"),
    ]

    operations = [
        migrations.RunPython(backfill_closed_to_resolved, reverse_backfill),
    ]
