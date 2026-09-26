"""Record the sponsorships that existed as a forever-boolean on Player.

Each one is recorded against the season it was approved in, so 2026-27
starts empty and everyone asks again, which is the whole point.
"""

from typing import Any

from django.db import migrations


def backfill(apps: Any, schema_editor: Any) -> None:
    Player = apps.get_model("server", "Player")  # noqa: N806
    Season = apps.get_model("server", "Season")  # noqa: N806
    ServiceRequest = apps.get_model("server", "ServiceRequest")  # noqa: N806
    SponsorshipGrant = apps.get_model("server", "SponsorshipGrant")  # noqa: N806
    Membership = apps.get_model("server", "Membership")  # noqa: N806

    def season_for(day: Any) -> Any:
        return (
            Season.objects.filter(start_date__lte=day, end_date__gte=day)
            .order_by("-start_date", "-id")
            .first()
        )

    requests = ServiceRequest.objects.filter(type="REQUEST_SPONSORED_MEMBERSHIP")
    current = Season.objects.filter(name="Season 2026-2027").first()

    # Pending requests are for the season now on sale.
    if current is not None:
        requests.filter(status="PENDING", season__isnull=True).update(season=current)

    # Decided requests: the season they were made in. Not updated_at, which
    # is auto_now and moves with any later admin save. Approved ones grant
    # that season to every player they named.
    granted = set()
    for request in requests.exclude(status="PENDING"):
        season = request.season or season_for(request.created_at.date())
        if season is None:
            continue
        if request.season_id is None:
            # update(), not save(), so updated_at is left as it was.
            ServiceRequest.objects.filter(pk=request.pk).update(season=season)
        if request.status != "APPROVED":
            continue
        for player in request.service_players.all():
            SponsorshipGrant.objects.get_or_create(
                player=player,
                season=season,
                defaults={"request": request, "note": "from an approved request"},
            )
            granted.add(player.pk)

    # Set by staff or an import, with no request behind it.
    fallback = Season.objects.filter(name="Season 2025-2026").first()
    if fallback is not None:
        for player in Player.objects.filter(sponsored=True).exclude(pk__in=granted):
            SponsorshipGrant.objects.get_or_create(
                player=player,
                season=fallback,
                defaults={"note": "set by staff before grants existed"},
            )

    # Anyone who has already bought 2026-27 at the discounted rate keeps it.
    if current is not None:
        paid = Membership.objects.filter(season=current, plan__type__slug="discounted")
        for player_id in paid.values_list("player_id", flat=True):
            SponsorshipGrant.objects.get_or_create(
                player_id=player_id,
                season=current,
                defaults={"note": "already paid the discounted rate"},
            )


class Migration(migrations.Migration):
    dependencies = [("server", "0150_sponsorship_grants")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
