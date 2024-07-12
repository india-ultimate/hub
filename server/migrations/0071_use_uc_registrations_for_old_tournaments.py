from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_uc_registrations_flag(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Tournament = apps.get_model("server", "Tournament")  # noqa: N806
    tournaments = Tournament.objects.all()

    for tournament in tournaments:
        # all older tournaments should use UCRegistrations to get roster info
        if tournament.use_uc_registrations is None:
            tournament.use_uc_registrations = True

    Tournament.objects.bulk_update(tournaments, ["use_uc_registrations"])


def unset_uc_registrations_flag(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Tournament = apps.get_model("server", "Tournament")  # noqa: N806
    tournaments = Tournament.objects.all()

    for tournament in tournaments:
        tournament.use_uc_registrations = None

    Tournament.objects.bulk_update(tournaments, ["use_uc_registrations"])


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0070_tournament_use_uc_registrations"),
    ]

    operations = [
        migrations.RunPython(
            code=set_uc_registrations_flag, reverse_code=unset_uc_registrations_flag
        ),
    ]
