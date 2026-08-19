from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("server", "0139_backfill_tournament_format"),
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
