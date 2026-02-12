# Backfill ticket category: set null/empty to "Other".

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_ticket_category(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Set category to 'Other' for tickets with null or empty category."""
    Ticket = apps.get_model("server", "Ticket")  # noqa: N806
    Ticket.objects.filter(category__isnull=True).update(category="Other")
    Ticket.objects.filter(category="").update(category="Other")


def reverse_backfill_ticket_category(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """No-op: cannot reliably restore which tickets were null vs had 'Other'."""


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0125_alter_ticket_category"),
    ]

    operations = [
        migrations.RunPython(backfill_ticket_category, reverse_backfill_ticket_category),
    ]
