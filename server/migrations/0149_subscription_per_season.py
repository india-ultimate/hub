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
        # Was nullable (on_delete=CASCADE); every row already has a season,
        # so no default is needed to tighten it.
        migrations.AlterField(
            model_name="subscription",
            name="season",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subscriptions",
                to="server.season",
            ),
        ),
        # A pure loosening (OneToOne -> ForeignKey), so it can't fail against
        # any data, and one player still holds at most one row, so the new
        # (player, season) uniqueness can't conflict with anything either.
        migrations.AlterField(
            model_name="subscription",
            name="player",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subscriptions",
                to="server.player",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="subscription",
            unique_together={("player", "season")},
        ),
    ]
