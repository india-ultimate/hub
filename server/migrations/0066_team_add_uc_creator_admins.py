from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_admins(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Team = apps.get_model("server", "Team")  # noqa: N806
    Player = apps.get_model("server", "Player")  # noqa: N806

    teams = Team.objects.all()
    for team in teams:
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
        migrations.RunPython(code=add_admins),
    ]
