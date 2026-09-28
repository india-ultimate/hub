import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("server", "0148_seed_catalog")]

    operations = [
        migrations.AddField(
            model_name="player",
            name="iu_id",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="server.subscriptionplan",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="amount_paid",
            field=models.PositiveIntegerField(blank=True, help_text="In paise.", null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="refunded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Nullable now, dropped in the follow-up deploy.
        migrations.AlterField(
            model_name="subscription",
            name="subscription_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        # The model no longer sets this, so new rows must be free to omit it.
        # Nullable now, dropped in the follow-up deploy.
        migrations.AlterField(
            model_name="subscription",
            name="is_annual",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="subscription",
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
            model_name="subscription",
            name="season",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="server.season",
            ),
        ),
    ]
