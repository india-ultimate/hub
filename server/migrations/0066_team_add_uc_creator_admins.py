from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_admins(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Team = apps.get_model("server", "Team")  # noqa: N806
    Player = apps.get_model("server", "Player")  # noqa: N806

    teams = Team.objects.exclude(ultimate_central_creator_id__isnull=True)
    for team in teams:
        if team.ultimate_central_creator_id is not None:
            try:
                player = Player.objects.get(ultimate_central_id=team.ultimate_central_creator_id)
                team.admins.add(player.user)
            except Player.DoesNotExist:
                continue


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0065_registration"),
    ]

    operations = [
        migrations.RunPython(code=add_admins, reverse_code=migrations.RunPython.noop),
    ]
