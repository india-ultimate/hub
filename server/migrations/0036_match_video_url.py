# Generated by Django 4.2.2 on 2023-10-05 17:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0035_tournament_logo_dark_tournament_logo_light"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="video_url",
            field=models.URLField(blank=True, max_length=255, null=True),
        ),
    ]
