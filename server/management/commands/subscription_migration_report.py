"""What migration 0150 will do, and what it cannot work out on its own."""

from typing import Any

from django.core.management.base import BaseCommand

from server.season.models import Season
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.subscription.models import Subscription
from server.transaction.models import RazorpayTransaction


class Command(BaseCommand):
    help = "Report what the subscription migration would change. Writes nothing."

    def handle(self, *args: Any, **options: Any) -> None:
        total = Subscription.objects.count()
        no_season = Subscription.objects.filter(season__isnull=True).count()
        unplaceable = [
            m
            for m in Subscription.objects.filter(season__isnull=True)
            if Season.containing(m.start_date) is None
        ]
        no_tier = Subscription.objects.filter(plan__isnull=True).count()
        with_event = Subscription.objects.filter(event__isnull=False).count()

        paid_pairs: set[tuple[int, int]] = set()
        for paid in RazorpayTransaction.objects.filter(
            status="completed", type="annual-subscription", season__isnull=False
        ):
            if paid.season_id is None:
                continue
            for player_id in paid.players.values_list("id", flat=True):
                paid_pairs.add((player_id, paid.season_id))
        held = set(Subscription.objects.values_list("player_id", "season_id"))
        recoverable = len(paid_pairs - held)

        never_paid = [
            m
            for m in Subscription.objects.select_related("season")
            if m.season_id and (m.player_id, m.season_id) not in paid_pairs
        ]

        self.stdout.write(self.style.SUCCESS(f"subscriptions:            {total}"))
        self.stdout.write(f"  with no season:       {no_season}")
        self.stdout.write(f"  with no tier:         {no_tier}")
        self.stdout.write(f"  with an event:        {with_event}")
        self.stdout.write(f"  recoverable history:  {recoverable}")
        self.stdout.write(f"  no completed payment: {len(never_paid)}  (kept, tier unknown)")

        # 0152 grants by created_at; an updated_at this late means a request
        # was edited after 2026-27 began, so check its season by hand.
        s26 = Season.objects.filter(name="Season 2026-2027").first()
        late = (
            ServiceRequest.objects.filter(
                type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
                status=ServiceRequestStatus.APPROVED,
                updated_at__date__gte=s26.start_date,
            ).count()
            if s26 is not None
            else 0
        )
        self.stdout.write(f"  approved sponsorships touched since 2026-27 began: {late}")

        if unplaceable:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{len(unplaceable)} rows fall in no season. Add a season "
                    "covering these dates before deploying:"
                )
            )
            for m in unplaceable[:20]:
                self.stdout.write(f"  subscription {m.pk}: {m.start_date}..{m.end_date}")
        else:
            self.stdout.write(self.style.SUCCESS("\nEvery row can be placed in a season."))

        self.stdout.write("\nFor staff to review by hand after the deploy:")
        for m in never_paid[:50]:
            self.stdout.write(
                f"  subscription {m.pk}  player {m.player_id}  {m.season}  "
                f"active={m.is_active}  waiver={m.waiver_valid}"
            )
