from importlib import import_module
from typing import Any

from django.db import migrations, models

# slug -> (short description for the card, features: one per line, "-" = not included)
COPY = {
    "community": (
        "For recreational players, coaches, team staff and supporters.",
        "Vote in state and national elections\n"
        "Join India Ultimate committees\n"
        "Coach, manage or staff a team at championships\n"
        "Coaching certifications and workshops\n"
        "Letters and certificates of participation\n"
        "IU newsletter and full access to the Hub\n"
        "- Playing in NCS tournaments and State and National Championships",
    ),
    "regular": (
        "For players competing in India Ultimate events.",
        "Everything in Community\n"
        "Play in NCS tournaments\n"
        "Play in State and National Championships\n"
        "Try out for state and national teams\n"
        "Play WFDF-recognised events through your club",
    ),
    "discounted": (
        "Everything in Regular, at a supported rate.",
        "Everything in Community\n"
        "Play in NCS tournaments\n"
        "Play in State and National Championships\n"
        "Try out for state and national teams\n"
        "Play WFDF-recognised events through your club",
    ),
    "patron": (
        "For players who want to give more back to the sport.",
        "Everything in Regular\nSupports the growth of flying disc in India at a higher rate",
    ),
}


def write_copy(apps: Any, schema_editor: Any) -> None:
    SubscriptionType = apps.get_model("server", "SubscriptionType")  # noqa: N806
    for slug, (description, features) in COPY.items():
        SubscriptionType.objects.filter(slug=slug).update(
            description=description, features=features
        )


def restore_descriptions(apps: Any, schema_editor: Any) -> None:
    SubscriptionType = apps.get_model("server", "SubscriptionType")  # noqa: N806
    tiers = import_module("server.migrations.0148_seed_catalog").TIERS
    for slug, _name, _grant, _order, _scopes, description in tiers:
        SubscriptionType.objects.filter(slug=slug).update(description=description)


class Migration(migrations.Migration):
    dependencies = [
        ("server", "0156_inflight_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptiontype",
            name="features",
            field=models.TextField(
                blank=True,
                help_text="One per line, shown as a checklist. Start a line with '-' for "
                "something this tier does not include.",
            ),
        ),
        migrations.RunPython(write_copy, restore_descriptions),
    ]
