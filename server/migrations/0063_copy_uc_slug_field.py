from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from server.utils import slugify_max


def copy_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Team = apps.get_model("server", "Team")  # noqa: N806
    for team in Team.objects.all():
        if team.ultimate_central_slug != "unknown":
            team.slug = slugify_max(team.ultimate_central_slug)
            team.save()


def reverse_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Team = apps.get_model("server", "Team")  # noqa: N806
    for team in Team.objects.all():
        team.slug = None
        team.save()


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0062_team_slug"),
    ]

    operations = [
        migrations.RunPython(code=copy_field, reverse_code=reverse_field),
    ]
