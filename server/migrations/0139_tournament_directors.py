"""Per-tournament directors, so managing an event does not need staff access."""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0138_tournament_agent"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="directors",
            field=models.ManyToManyField(
                blank=True,
                related_name="directed_tournaments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
