from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0055_create_tournament_fields"),
    ]

    operations = [
        migrations.RemoveField(model_name="match", name="field"),
        migrations.RenameField(model_name="match", old_name="field_reference", new_name="field"),
    ]
