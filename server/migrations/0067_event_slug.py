# Generated by Django 4.2.2 on 2024-07-05 14:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0066_team_add_uc_creator_admins"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="slug",
            field=models.SlugField(blank=True, null=True),
        ),
    ]
