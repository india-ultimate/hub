import datetime

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_player_registration_dates(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    events = Event.objects.all()

    for event in events:
        if not event.player_registration_start_date:
            event.player_registration_start_date = (
                event.team_registration_end_date + datetime.timedelta(days=1)
            )

        if not event.player_registration_end_date:
            event.player_registration_end_date = event.start_date - datetime.timedelta(days=1)

    Event.objects.bulk_update(
        events, (["player_registration_start_date", "player_registration_end_date"])
    )


def remove_player_registration_dates(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    events = Event.objects.all()

    for event in events:
        event.player_registration_start_date = None
        event.player_registration_end_date = None

    Event.objects.bulk_update(
        events, (["player_registration_start_date", "player_registration_end_date"])
    )


class Migration(migrations.Migration):
    dependencies = [("server", "0072_event_player_registration_end_date_and_more")]

    operations = [
        migrations.RunPython(
            code=add_player_registration_dates, reverse_code=remove_player_registration_dates
        )
    ]
