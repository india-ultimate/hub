import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0166_rosterswap"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscription",
            name="coc_agreed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="subscription",
            name="coc_agreed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="subscription",
            name="coc_agreed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="coc_agreed_subscriptions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
