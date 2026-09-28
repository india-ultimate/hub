"""Make the transaction-players link a model, so a line can say what it bought.

The table is the one Django already created for the many-to-many, so no row
moves: Django is told the model exists, and only the new columns are added.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("server", "0153_series_roles")]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="RazorpayTransactionPlayer",
                    fields=[
                        # The auto-created table's key is a bigint, as the
                        # production schema confirms. State only; no ALTER.
                        ("id", models.BigAutoField(primary_key=True, serialize=False)),
                        (
                            "transaction",
                            models.ForeignKey(
                                db_column="razorpaytransaction_id",
                                on_delete=django.db.models.deletion.CASCADE,
                                to="server.razorpaytransaction",
                            ),
                        ),
                        (
                            "player",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE, to="server.player"
                            ),
                        ),
                    ],
                    options={
                        "db_table": "server_razorpaytransaction_players",
                        "unique_together": {("transaction", "player")},
                    },
                ),
                migrations.AlterField(
                    model_name="razorpaytransaction",
                    name="players",
                    field=models.ManyToManyField(
                        through="server.RazorpayTransactionPlayer", to="server.player"
                    ),
                ),
            ],
            database_operations=[],
        ),
        migrations.AddField(
            model_name="razorpaytransactionplayer",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="server.subscriptionplan",
            ),
        ),
        migrations.AddField(
            model_name="razorpaytransactionplayer",
            name="amount",
            field=models.PositiveIntegerField(blank=True, help_text="In paise.", null=True),
        ),
        migrations.AddField(
            model_name="razorpaytransactionplayer",
            name="subscription",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="server.subscription",
            ),
        ),
        migrations.AddField(
            model_name="razorpaytransactionplayer",
            name="needs_review",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="razorpaytransactionplayer",
            name="review_note",
            field=models.TextField(blank=True),
        ),
        migrations.AlterModelOptions(
            name="razorpaytransaction",
            options={"permissions": [("refund_razorpaytransaction", "Can refund payments")]},
        ),
    ]
