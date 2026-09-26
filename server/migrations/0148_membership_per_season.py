import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("server", "0147_seed_catalog")]

    operations = [
        migrations.AddField(
            model_name="player",
            name="membership_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="membership",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="server.membershipplan",
            ),
        ),
        migrations.AddField(
            model_name="membership",
            name="amount_paid",
            field=models.PositiveIntegerField(blank=True, help_text="In paise.", null=True),
        ),
        migrations.AddField(
            model_name="membership",
            name="refunded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Nullable now, dropped in the follow-up deploy.
        migrations.AlterField(
            model_name="membership",
            name="membership_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        # The model no longer sets this, so new rows must be free to omit it.
        # Nullable now, dropped in the follow-up deploy.
        migrations.AlterField(
            model_name="membership",
            name="is_annual",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="membership",
            name="event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="server.event",
            ),
        ),
        # Still nullable: production has 697 rows with no season at all.
        # Task 5's migration buckets every one of them by its start date
        # before tightening this to non-null -- doing it here would refuse
        # to apply against real data.
        migrations.AlterField(
            model_name="membership",
            name="season",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="memberships",
                to="server.season",
            ),
        ),
    ]
