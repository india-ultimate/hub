# Generated by Django 4.2.2 on 2023-08-30 12:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0024_team_ultimate_central_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="imported_data",
            field=models.BooleanField(default=False),
        ),
    ]
