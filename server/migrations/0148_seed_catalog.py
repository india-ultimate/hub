"""Seed the subscription catalog: the four tiers, their scopes, and their
prices per season.

Past seasons' plans are seeded is_available=False, so nothing historical can
be bought; only Season 2026-2027 is on sale. The legacy seasons from Task 1
(2022-2023, 2023-2024) get no plans at all -- they predate the catalog.
"""

from typing import Any

from django.db import migrations

PLAY = "play_championships"
STAFF = "staff_championships"
VOTE = "vote"

TIERS = [
    # slug, name, requires_grant, display_order, scopes, description
    (
        "patron",
        "Patron Subscription",
        False,
        1,
        [PLAY, STAFF, VOTE],
        "Everything in Community, plus playing in NCS tournaments and State "
        "and National Championships, and supporting the sport at a higher rate.",
    ),
    (
        "regular",
        "Regular Subscription",
        False,
        2,
        [PLAY, STAFF, VOTE],
        "Everything in Community, plus playing in NCS tournaments and State "
        "and National Championships.",
    ),
    (
        "discounted",
        "Discounted Subscription",
        True,
        3,
        [PLAY, STAFF, VOTE],
        "Everything in a Regular subscription, at a reduced rate. Needs approval.",
    ),
    (
        "community",
        "Community Subscription",
        False,
        4,
        [STAFF, VOTE],
        "For recreational players, non-playing staff and supporters of India "
        "Ultimate. Take part in coaching certifications and workshops; vote in "
        "state and national elections and join committees; receive letters and "
        "certificates; get updates and content on the Hub; and contribute to "
        "the growth of flying disc in India. Does not include playing in NCS "
        "tournaments or State and National Championships.",
    ),
]

# season name -> {tier slug: amount in paise}. Past seasons come from the old
# columns on Season; 2026-27 is the new price list.
PLANS = {
    "Season 2024-2025": {"regular": 70000, "discounted": 20000},
    "Season 2025-2026": {"patron": 150000, "regular": 75000, "discounted": 25000},
    "Season 2026-2027": {
        "patron": 150000,
        "regular": 75000,
        "discounted": 30000,
        "community": 25000,
    },
}

ON_SALE = {"Season 2026-2027"}


def seed(apps: Any, schema_editor: Any) -> None:
    SubscriptionType = apps.get_model("server", "SubscriptionType")  # noqa: N806
    SubscriptionTypeScope = apps.get_model("server", "SubscriptionTypeScope")  # noqa: N806
    SubscriptionPlan = apps.get_model("server", "SubscriptionPlan")  # noqa: N806
    Season = apps.get_model("server", "Season")  # noqa: N806

    tiers = {}
    for slug, name, requires_grant, order, scopes, description in TIERS:
        tier, _ = SubscriptionType.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "requires_grant": requires_grant,
                "display_order": order,
                "description": description,
            },
        )
        tiers[slug] = tier
        for scope in scopes:
            SubscriptionTypeScope.objects.get_or_create(type=tier, scope=scope)

    for season_name, amounts in PLANS.items():
        season = Season.objects.filter(name=season_name).first()
        if season is None:
            # Task 1's 0146_legacy_seasons get_or_creates every season named
            # here, in every database including test. A miss means a broken
            # deploy, not a season to seed around quietly.
            raise RuntimeError(f"Season {season_name!r} does not exist; expected by Task 1")
        for slug, amount in amounts.items():
            SubscriptionPlan.objects.get_or_create(
                season=season,
                type=tiers[slug],
                defaults={"amount": amount, "is_available": season_name in ON_SALE},
            )


def unseed(apps: Any, schema_editor: Any) -> None:
    """Remove only what seed() created, not whatever staff added since.

    A bare `.objects.all().delete()` here would also wipe plans copy_plans()
    made for later seasons, and any plans a later task adds -- this migration
    never created those, so rolling it back must not destroy them.
    """
    slugs = [slug for slug, *_rest in TIERS]
    apps.get_model("server", "SubscriptionPlan").objects.filter(season__name__in=PLANS).delete()
    apps.get_model("server", "SubscriptionTypeScope").objects.filter(type__slug__in=slugs).delete()
    apps.get_model("server", "SubscriptionType").objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [("server", "0147_subscription_catalog")]
    operations = [migrations.RunPython(seed, unseed)]
