# Generated by Django 4.2.2 on 2024-01-19 08:02

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0051_user_is_tournament_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="duration_mins",
            field=models.PositiveIntegerField(default=75),
        ),
    ]
