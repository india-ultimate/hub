# Generated by Django 4.2.2 on 2024-03-04 18:55

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0056_match_rename_field_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournamentfield",
            name="address",
            field=models.CharField(blank=True, max_length=25, null=True),
        ),
    ]
