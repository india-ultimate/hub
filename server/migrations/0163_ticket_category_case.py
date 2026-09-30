from typing import Any

from django.db import migrations


def normalise(apps: Any, schema_editor: Any) -> None:
    # Before categories were validated, one ticket was saved as "other", which
    # the category filter's exact match would never find.
    Ticket = apps.get_model("server", "Ticket")  # noqa: N806
    Ticket.objects.filter(category="other").update(category="Other")


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0162_ticket_upvoters"),
    ]

    operations = [
        migrations.RunPython(normalise, migrations.RunPython.noop),
    ]
