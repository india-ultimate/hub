# Generated by Django 4.2.2 on 2024-01-27 11:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0053_commentaryinfo"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchStats",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("score_team_1", models.PositiveIntegerField(default=0)),
                ("score_team_2", models.PositiveIntegerField(default=0)),
                (
                    "match",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stats",
                        to="server.match",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MatchStatsScoreEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assist_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assist_score_events",
                        to="server.player",
                    ),
                ),
                (
                    "goal_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="goal_score_events",
                        to="server.player",
                    ),
                ),
                (
                    "match_stat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="score_events",
                        to="server.matchstats",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="score_events",
                        to="server.team",
                    ),
                ),
            ],
        ),
    ]
