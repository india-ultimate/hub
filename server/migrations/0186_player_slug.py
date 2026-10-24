from typing import Any

from django.db import migrations, models

from server.player_profile.slugs import slug_base, unique_slug


def backfill_slugs(apps: Any, schema_editor: Any) -> None:
    Player = apps.get_model("server", "Player")
    taken: set[str] = set()
    players = list(Player.objects.select_related("user").order_by("id"))
    for player in players:
        player.slug = unique_slug(slug_base(player.user.first_name, player.user.last_name), taken)
        taken.add(player.slug)
    Player.objects.bulk_update(players, ["slug"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0185_announcement_tech_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="slug",
            field=models.SlugField(blank=True, max_length=60, null=True, unique=True),
        ),
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
