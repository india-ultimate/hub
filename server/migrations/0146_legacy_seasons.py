"""A gap-free season timeline from 2022, so every subscription has a season.

The 697 rows with no season run April-March and June-May, before the
August-July seasons already in production, so the two legacy seasons below
close that gap. The three real seasons are get_or_create'd too: production
already has them under these exact names, so this is a no-op there, while
dev and test databases, which don't, gain them.
"""

from typing import Any

from django.db import migrations

SEASONS = [
    ("Season 2022-2023", "2022-04-01", "2023-05-31", 0, 0, 0),
    ("Season 2023-2024", "2023-06-01", "2024-07-31", 0, 0, 0),
    ("Season 2024-2025", "2024-08-01", "2025-07-31", 70000, 20000, 0),
    ("Season 2025-2026", "2025-08-01", "2026-07-31", 75000, 25000, 150000),
    ("Season 2026-2027", "2026-08-01", "2027-07-31", 75000, 25000, 150000),
]

LEGACY_NAMES = ["Season 2022-2023", "Season 2023-2024"]


def add_seasons(apps: Any, schema_editor: Any) -> None:
    Season = apps.get_model("server", "Season")  # noqa: N806
    for name, start, end, annual, sponsored, supporter in SEASONS:
        Season.objects.get_or_create(
            name=name,
            defaults={
                "start_date": start,
                "end_date": end,
                "annual_subscription_amount": annual,
                "sponsored_annual_subscription_amount": sponsored,
                "supporter_annual_subscription_amount": supporter,
            },
        )


def remove_legacy_seasons(apps: Any, schema_editor: Any) -> None:
    """Only the two legacy seasons -- the three real ones predate this migration."""
    Season = apps.get_model("server", "Season")  # noqa: N806
    Season.objects.filter(name__in=LEGACY_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [("server", "0145_subscriptions")]
    operations = [migrations.RunPython(add_seasons, remove_legacy_seasons)]
