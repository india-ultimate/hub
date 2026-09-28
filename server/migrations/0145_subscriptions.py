"""Rename membership to subscription: the table, its columns and stored values.

A rename keeps every row, index and foreign key. The values below live in
rows written before this change, so they are rewritten here, before any
later migration filters on the new names.
"""

from typing import Any

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

STORED = [
    ("RazorpayTransaction", "type", "annual-membership", "annual-subscription"),
    ("ServiceRequest", "type", "REQUEST_SPONSORED_MEMBERSHIP", "REQUEST_SPONSORED_SUBSCRIPTION"),
    ("Ticket", "category", "Membership", "Subscription"),
]


def rename_stored_values(apps: Any, schema_editor: Any) -> None:
    for model, field, old, new in STORED:
        apps.get_model("server", model).objects.filter(**{field: old}).update(**{field: new})
    # Django renames the content type with the model, but not its permission
    # rows. A group holding view_membership must keep that access.
    Permission = apps.get_model("auth", "Permission")  # noqa: N806
    for perm in Permission.objects.filter(
        content_type__app_label="server", codename__endswith="_membership"
    ):
        perm.codename = perm.codename.replace("_membership", "_subscription")
        perm.name = perm.name.replace("membership", "subscription")
        perm.save(update_fields=["codename", "name"])


def restore_stored_values(apps: Any, schema_editor: Any) -> None:
    for model, field, old, new in STORED:
        apps.get_model("server", model).objects.filter(**{field: new}).update(**{field: old})
    Permission = apps.get_model("auth", "Permission")  # noqa: N806
    for perm in Permission.objects.filter(
        content_type__app_label="server", codename__endswith="_subscription"
    ):
        perm.codename = perm.codename.replace("_subscription", "_membership")
        perm.name = perm.name.replace("subscription", "membership")
        perm.save(update_fields=["codename", "name"])


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("server", "0144_backfill_player_teams"),
    ]

    operations = [
        migrations.RenameModel("Membership", "Subscription"),
        migrations.RenameField("subscription", "membership_number", "subscription_number"),
        migrations.RenameField("event", "is_membership_needed", "is_subscription_needed"),
        migrations.RenameField("season", "annual_membership_amount", "annual_subscription_amount"),
        migrations.RenameField(
            "season", "sponsored_annual_membership_amount", "sponsored_annual_subscription_amount"
        ),
        migrations.RenameField(
            "season", "supporter_annual_membership_amount", "supporter_annual_subscription_amount"
        ),
        migrations.AlterField(
            model_name="clustermember",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="duplicate_cluster_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="razorpaytransaction",
            name="type",
            field=models.CharField(
                choices=[
                    ("annual-subscription", "Annual Subscription"),
                    ("team-reg", "Team Registration"),
                    ("partial-team-reg", "Partial Team Registration"),
                    ("player-reg", "Player Registration"),
                    ("form-payment", "Form Payment"),
                ],
                default="annual-subscription",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="servicerequest",
            name="type",
            field=models.CharField(
                choices=[
                    ("REQUEST_SPONSORED_SUBSCRIPTION", "Request Sponsored Subscription"),
                    ("REQUEST_ACCOUNT_MERGE", "Merge accounts"),
                ],
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="ticket",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Account", "Account"),
                    ("Competitions", "Competitions"),
                    ("Subscription", "Subscription"),
                    ("Tournament", "Tournament"),
                    ("Payment", "Payment"),
                    ("Tech", "Tech"),
                    ("Other", "Other"),
                ],
                default="Other",
                max_length=100,
                null=True,
            ),
        ),
        migrations.RunPython(rename_stored_values, restore_stored_values),
    ]
