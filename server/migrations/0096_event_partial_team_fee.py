# Generated by Django 4.2.2 on 2024-10-09 17:54

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0095_tournament_partial_teams"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="partial_team_fee",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
