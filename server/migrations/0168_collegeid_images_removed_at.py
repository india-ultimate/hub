from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0167_subscription_code_of_conduct"),
    ]

    operations = [
        migrations.AddField(
            model_name="collegeid",
            name="images_removed_at",
            field=models.DateField(blank=True, null=True),
        ),
    ]
