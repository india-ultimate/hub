# Generated by Django 4.2.2 on 2023-08-07 13:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0015_rename_vaccination_certificate_vaccination_certificate_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="membership",
            name="waiver_signed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="membership",
            name="waiver_signed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
