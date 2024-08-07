# Generated by Django 4.2.2 on 2024-07-05 13:17

import django.db.models.deletion
import django_prometheus.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0064_event_registration_end_date_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Registration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("is_playing", models.BooleanField(default=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("DFLT", "Default"),
                            ("CAP", "Captain"),
                            ("SCAP", "Spirit Captain"),
                            ("COACH", "Coach"),
                            ("ACOACH", "Assistant Coach"),
                            ("MNGR", "Manager"),
                        ],
                        default="DFLT",
                        max_length=6,
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="server.event"
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="server.player"
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="server.team"
                    ),
                ),
            ],
            bases=(
                django_prometheus.models.ExportModelOperationsMixin("registration"),
                models.Model,
            ),
        ),
    ]
