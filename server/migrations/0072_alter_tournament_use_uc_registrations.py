# Generated by Django 4.2.2 on 2024-07-12 13:15

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0071_use_uc_registrations_for_old_tournaments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournament",
            name="use_uc_registrations",
            field=models.BooleanField(default=False),
        ),
    ]