# Generated by Django 4.2.2 on 2024-07-19 04:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0078_player_registrations_non_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="spiritscore",
            name="msp_v2",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="msp_v2",
                to="server.player",
            ),
        ),
        migrations.AddField(
            model_name="spiritscore",
            name="mvp_v2",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="mvp_v2",
                to="server.player",
            ),
        ),
    ]