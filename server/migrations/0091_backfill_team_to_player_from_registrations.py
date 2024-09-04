from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_team_to_player_from_registrations(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    SeriesRegistration = apps.get_model("server", "SeriesRegistration")  # noqa: N806
    series_registrations = SeriesRegistration.objects.all()

    Registration = apps.get_model("server", "Registration")  # noqa: N806
    registrations = Registration.objects.all()

    for series_registration in series_registrations:
        series_registration.player.teams.add(series_registration.team)

    for registration in registrations:
        registration.player.teams.add(registration.team)


class Migration(migrations.Migration):
    dependencies = [("server", "0090_alter_player_teams")]

    operations = [
        migrations.RunPython(
            code=add_team_to_player_from_registrations, reverse_code=migrations.RunPython.noop
        )
    ]
