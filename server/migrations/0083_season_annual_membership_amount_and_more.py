# Generated by Django 4.2.2 on 2024-08-15 16:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0082_razorpaytransaction_season"),
    ]

    operations = [
        migrations.AddField(
            model_name="season",
            name="annual_membership_amount",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="season",
            name="sponsored_annual_membership_amount",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
