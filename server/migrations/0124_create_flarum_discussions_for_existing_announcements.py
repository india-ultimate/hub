# The forum is gone; this historical migration no longer does anything.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0123_announcement_forum_discussion_id"),
    ]

    operations = [
        migrations.RunPython(
            code=migrations.RunPython.noop,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
