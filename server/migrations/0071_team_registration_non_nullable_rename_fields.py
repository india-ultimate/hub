from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("server", "0070_backfill_registration_start_end_dates")]

    operations = [
        migrations.AlterField(
            model_name="event", name="registration_start_date", field=models.DateField()
        ),
        migrations.AlterField(
            model_name="event", name="registration_end_date", field=models.DateField()
        ),
        migrations.RenameField(
            model_name="event",
            old_name="registration_start_date",
            new_name="team_registration_start_date",
        ),
        migrations.RenameField(
            model_name="event",
            old_name="registration_end_date",
            new_name="team_registration_end_date",
        ),
    ]
