from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def copy_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Team = apps.get_model("server", "Team")  # noqa: N806
    Team.objects.all().update(slug=F("ultimate_central_slug"))


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0062_team_slug"),
    ]

    operations = [
        migrations.RunPython(code=copy_field),
    ]
