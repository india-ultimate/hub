from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from server.utils import slugify_max


def copy_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    for event in Event.objects.all():
        if event.ultimate_central_slug != "unknown":
            event.slug = slugify_max(event.ultimate_central_slug)
            event.save()


def reverse_field(apps: StateApps, schema: BaseDatabaseSchemaEditor) -> None:
    Event = apps.get_model("server", "Event")  # noqa: N806
    for event in Event.objects.all():
        event.slug = None
        event.save()


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0067_event_slug"),
    ]

    operations = [
        migrations.RunPython(code=copy_field, reverse_code=reverse_field),
    ]
