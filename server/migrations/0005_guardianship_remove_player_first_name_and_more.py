# Generated by Django 4.2.2 on 2023-07-12 03:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0004_alter_player_state_ut"),
    ]

    operations = [
        migrations.CreateModel(
            name="Guardianship",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "relation",
                    models.TextField(
                        choices=[("MO", "Mother"), ("FA", "Father"), ("LG", "Legal Guardian")],
                        max_length=2,
                    ),
                ),
            ],
        ),
        migrations.RemoveField(
            model_name="player",
            name="first_name",
        ),
        migrations.RemoveField(
            model_name="player",
            name="guardian",
        ),
        migrations.RemoveField(
            model_name="player",
            name="last_name",
        ),
        migrations.DeleteModel(
            name="Guardian",
        ),
        migrations.AddField(
            model_name="guardianship",
            name="player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="server.player"
            ),
        ),
        migrations.AddField(
            model_name="guardianship",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterUniqueTogether(
            name="guardianship",
            unique_together={("user", "player")},
        ),
    ]
