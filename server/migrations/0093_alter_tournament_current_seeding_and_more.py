# Generated by Django 4.2.2 on 2024-09-12 06:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0092_event_player_fee_event_team_fee"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournament",
            name="current_seeding",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="initial_seeding",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="tournament",
            name="spirit_ranking",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
