# Generated by Django 4.2.2 on 2025-03-17 15:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0101_registration_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="tier",
            field=models.IntegerField(default=4),
        ),
    ]
