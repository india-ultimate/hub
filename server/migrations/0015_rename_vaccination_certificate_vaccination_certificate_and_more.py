# Generated by Django 4.2.2 on 2023-07-30 03:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0014_remove_razorpaytransaction_membership_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="vaccination",
            old_name="vaccination_certificate",
            new_name="certificate",
        ),
        migrations.RemoveField(
            model_name="vaccination",
            name="vaccination_name",
        ),
        migrations.AddField(
            model_name="vaccination",
            name="name",
            field=models.CharField(
                blank=True,
                choices=[
                    ("CVSHLD", "Covishield"),
                    ("CVXN", "Covaxin"),
                    ("MDRN", "Moderna"),
                    ("SPTNK", "Sputnik"),
                    ("JNJ", "Johnson & Johnson"),
                ],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="vaccination",
            name="explain_not_vaccinated",
            field=models.TextField(blank=True, null=True),
        ),
    ]
