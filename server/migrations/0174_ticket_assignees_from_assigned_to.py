from typing import Any

from django.db import migrations


def copy_assigned_to(apps: Any, schema_editor: Any) -> None:
    Ticket = apps.get_model("server", "Ticket")
    for ticket in Ticket.objects.filter(assigned_to__isnull=False):
        ticket.assignees.add(ticket.assigned_to_id)


class Migration(migrations.Migration):

    dependencies = [
        ("server", "0173_committees"),
    ]

    operations = [
        migrations.RunPython(copy_assigned_to, migrations.RunPython.noop),
    ]
