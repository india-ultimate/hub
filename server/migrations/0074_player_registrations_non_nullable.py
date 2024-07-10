from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("server", "0073_backfill_player_registration_dates")]

    operations = [
        migrations.AlterField(
            model_name="event", name="player_registration_start_date", field=models.DateField()
        ),
        migrations.AlterField(
            model_name="event", name="player_registration_end_date", field=models.DateField()
        ),
    ]
