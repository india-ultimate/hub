from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F

from server.utils import slugify_max


def copy_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    Event.objects.all().update(slug=slugify_max(str(F("ultimate_central_slug"))))


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0067_event_slug"),
    ]

    operations = [
        migrations.RunPython(code=copy_field),
    ]
