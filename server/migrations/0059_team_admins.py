# Generated by Django 4.2.2 on 2024-06-28 14:31

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0058_alter_player_occupation_collegeid"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="admins",
            field=models.ManyToManyField(related_name="admin_teams", to=settings.AUTH_USER_MODEL),
        ),
    ]
