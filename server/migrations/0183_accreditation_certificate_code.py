import django.core.validators
from dateutil.relativedelta import relativedelta
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

import server.accreditation.models


def set_expiry_dates(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Accreditation = apps.get_model("server", "Accreditation")
    accreditations = list(Accreditation.objects.all())
    for accreditation in accreditations:
        accreditation.expiry_date = accreditation.date + relativedelta(months=18)
    Accreditation.objects.bulk_update(accreditations, ["expiry_date"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0182_can_create_forms"),
    ]

    operations = [
        migrations.AddField(
            model_name="accreditation",
            name="certificate_code",
            field=models.CharField(
                blank=True,
                error_messages={
                    "unique": "This Certificate Code is already on another player's profile."
                },
                max_length=12,
                null=True,
                unique=True,
                validators=[django.core.validators.RegexValidator("^[0-9]{10}[A-Z0-9]{2}$")],
            ),
        ),
        migrations.AddField(
            model_name="accreditation",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(set_expiry_dates, migrations.RunPython.noop, elidable=True),
        migrations.AlterField(
            model_name="accreditation",
            name="is_valid",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="accreditation",
            name="date",
            field=models.DateField(validators=[server.accreditation.models.not_in_the_future]),
        ),
    ]
