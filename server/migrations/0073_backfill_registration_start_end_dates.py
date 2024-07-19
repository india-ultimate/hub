import datetime

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_registration_dates(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    events = Event.objects.all()

    for event in events:
        if not event.registration_start_date:
            event.registration_start_date = event.start_date - datetime.timedelta(days=14)
        if not event.registration_end_date:
            event.registration_end_date = event.start_date - datetime.timedelta(days=7)

    Event.objects.bulk_update(events, (["registration_start_date", "registration_end_date"]))


def remove_registration_dates(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    events = Event.objects.all()

    for event in events:
        event.registration_start_date = None
        event.registration_end_date = None

    Event.objects.bulk_update(events, (["registration_start_date", "registration_end_date"]))


class Migration(migrations.Migration):
    dependencies = [("server", "0072_alter_tournament_use_uc_registrations")]

    operations = [
        migrations.RunPython(code=add_registration_dates, reverse_code=remove_registration_dates)
    ]
