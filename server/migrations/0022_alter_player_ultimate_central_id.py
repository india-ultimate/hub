# Generated by Django 4.2.2 on 2023-08-24 12:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0021_player_sponsored"),
    ]

    operations = [
        migrations.AlterField(
            model_name="player",
            name="ultimate_central_id",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True, unique=True),
        ),
    ]
