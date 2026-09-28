import datetime
import importlib
import io

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase

from server.core.models import Player
from server.season.models import Season
from server.servicerequests.models import (
    ServiceRequest,
    ServiceRequestStatus,
    ServiceRequestType,
)
from server.subscription import catalog, sponsorship
from server.subscription.models import SponsorshipGrant, Subscription

from .test_subscription_model import make_player

backfill = importlib.import_module("server.migrations.0152_backfill_grants")


class TestGrants(TestCase):
    def setUp(self) -> None:
        self.s25 = Season.objects.get(name="Season 2025-2026")
        self.s26 = Season.objects.get(name="Season 2026-2027")
        self.player = make_player("i@example.com")

    def test_a_grant_counts_only_for_its_own_season(self) -> None:
        sponsorship.grant(self.player, self.s25)
        self.assertTrue(sponsorship.has_grant(self.player, self.s25))
        self.assertFalse(sponsorship.has_grant(self.player, self.s26))

    def test_granting_twice_changes_nothing(self) -> None:
        first = sponsorship.grant(self.player, self.s26)
        second = sponsorship.grant(self.player, self.s26)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SponsorshipGrant.objects.count(), 1)

    def test_approving_a_request_grants_its_season(self) -> None:
        user = self.player.user
        request = ServiceRequest.objects.create(
            user=user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="please",
            season=self.s26,
        )
        request.service_players.add(self.player)

        request.status = ServiceRequestStatus.APPROVED
        request.save()

        self.assertTrue(sponsorship.has_grant(self.player, self.s26))

    def test_resaving_an_approved_request_does_not_grant_twice(self) -> None:
        user = self.player.user
        request = ServiceRequest.objects.create(
            user=user,
            type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
            message="please",
            season=self.s26,
        )
        request.service_players.add(self.player)
        request.status = ServiceRequestStatus.APPROVED
        request.save()
        request.save()

        self.assertEqual(
            SponsorshipGrant.objects.filter(player=self.player, season=self.s26).count(), 1
        )


class TestSeasonWithNoPlans(TestCase):
    def test_a_season_nobody_has_priced_yet_offers_nothing(self) -> None:
        empty = Season.objects.create(
            name="Season 2030-2031", start_date="2030-08-01", end_date="2031-07-31"
        )
        self.assertEqual(list(catalog.plans_for(empty)), [])
        self.assertIsNone(catalog.plan_for(empty, "regular"))


class TestRequestingSponsorship(TestCase):
    def setUp(self) -> None:
        self.player = make_player("j@example.com")
        self.client.force_login(self.player.user)

    def request_for(self, season_id: int | None) -> tuple[int, dict[str, object]]:
        response = self.client.post(
            "/api/service-requests/",
            data={
                "type": ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION,
                "message": "please",
                "service_player_ids": [self.player.id],
                "season_id": season_id,
            },
            content_type="application/json",
        )
        return response.status_code, response.json()

    def test_a_request_names_the_season_it_is_for(self) -> None:
        s26 = Season.objects.get(name="Season 2026-2027")
        status, body = self.request_for(s26.id)
        self.assertEqual(status, 200)
        self.assertEqual(body["season"], s26.id)

    def test_a_season_with_no_discounted_tier_on_sale_is_refused(self) -> None:
        # 2025-26's plans are seeded but no longer on sale.
        s25 = Season.objects.get(name="Season 2025-2026")
        self.assertEqual(self.request_for(s25.id)[0], 400)
        self.assertEqual(self.request_for(None)[0], 400)
        self.assertFalse(ServiceRequest.objects.exists())


class TestBackfill(TestCase):
    def setUp(self) -> None:
        self.s25 = Season.objects.get(name="Season 2025-2026")
        self.s26 = Season.objects.get(name="Season 2026-2027")

    def sponsorship_request(
        self, player: Player, status: str, updated: datetime.date = datetime.date(2025, 11, 2)
    ) -> ServiceRequest:
        request = ServiceRequest.objects.create(
            user=player.user, type=ServiceRequestType.REQUEST_SPONSORED_SUBSCRIPTION, message="-"
        )
        request.service_players.add(player)
        # A queryset update skips the signal, as the old data never had grants.
        ServiceRequest.objects.filter(pk=request.pk).update(
            status=status,
            # timezone.utc, not datetime.UTC: CI runs Python 3.10.
            created_at=datetime.datetime(2025, 11, 1, tzinfo=datetime.timezone.utc),
            updated_at=datetime.datetime.combine(updated, datetime.time(), datetime.timezone.utc),
        )
        request.refresh_from_db()
        return request

    def test_history_becomes_last_seasons_grants_and_this_season_starts_empty(self) -> None:
        approved = make_player("approved@example.com")
        approved_request = self.sponsorship_request(approved, ServiceRequestStatus.APPROVED)
        Player.objects.filter(pk=approved.pk).update(sponsored=True)
        by_staff = make_player("staff@example.com")
        Player.objects.filter(pk=by_staff.pk).update(sponsored=True)
        rejected_request = self.sponsorship_request(
            make_player("rejected@example.com"), ServiceRequestStatus.REJECTED
        )
        pending_request = self.sponsorship_request(
            make_player("pending@example.com"), ServiceRequestStatus.PENDING
        )
        # Approved in 2025-26, then edited by staff after 2026-27 began.
        edited = make_player("edited@example.com")
        edited_request = self.sponsorship_request(
            edited, ServiceRequestStatus.APPROVED, updated=datetime.date(2026, 9, 1)
        )
        paid = make_player("paid@example.com")
        Subscription.objects.create(
            player=paid,
            season=self.s26,
            plan=catalog.plan_for(self.s26, catalog.DISCOUNTED),
            start_date=self.s26.start_date,
            end_date=self.s26.end_date,
        )

        report = io.StringIO()
        call_command("subscription_migration_report", stdout=report)
        self.assertIn("approved sponsorships touched since 2026-27 began: 1", report.getvalue())

        backfill.backfill(apps, None)

        grants = {(g.player_id, g.season_id) for g in SponsorshipGrant.objects.all()}
        self.assertEqual(
            grants,
            {
                (approved.pk, self.s25.pk),
                (by_staff.pk, self.s25.pk),
                (edited.pk, self.s25.pk),
                (paid.pk, self.s26.pk),
            },
        )
        self.assertEqual(SponsorshipGrant.objects.get(player=approved).request, approved_request)
        approved_request.refresh_from_db()
        rejected_request.refresh_from_db()
        pending_request.refresh_from_db()
        self.assertEqual(approved_request.season, self.s25)
        self.assertEqual(rejected_request.season, self.s25)
        self.assertEqual(pending_request.season, self.s26)
        # Stamping the season leaves the decision date alone.
        stamped_at = edited_request.updated_at
        edited_request.refresh_from_db()
        self.assertEqual(edited_request.season, self.s25)
        self.assertEqual(edited_request.updated_at, stamped_at)

        backfill.backfill(apps, None)
        self.assertEqual(SponsorshipGrant.objects.count(), len(grants))


class TestResetEmail(TestCase):
    def setUp(self) -> None:
        self.s26 = Season.objects.get(name="Season 2026-2027")
        self.lost = make_player("lost@example.com")
        self.lost.sponsored = True
        self.lost.save(update_fields=["sponsored"])

    def recipients(self) -> list[str]:
        from server.task.models import Task

        queued = Task.objects.filter(type=Task.TaskType.SEND_EMAIL)
        return [task.data["to"][0] for task in queued]

    def test_only_people_who_lost_sponsorship_are_written_to(self) -> None:
        kept = make_player("kept@example.com")
        kept.sponsored = True
        kept.save(update_fields=["sponsored"])
        sponsorship.grant(kept, self.s26)

        blank = make_player("blank@example.com")
        blank.sponsored = True
        blank.save(update_fields=["sponsored"])
        blank.user.email = ""
        blank.user.save(update_fields=["email"])

        make_player("never@example.com")

        call_command("email_sponsorship_reset", stdout=io.StringIO())

        self.assertEqual(self.recipients(), ["lost@example.com"])

    def test_the_email_names_the_season_and_links_the_subscription_page(self) -> None:
        from server.task.models import Task

        call_command("email_sponsorship_reset", stdout=io.StringIO())

        html = Task.objects.get().data["html_content"]
        self.assertIn("Season 2026-2027", html)
        self.assertIn(f"/subscription/{self.lost.pk}", html)

    def test_a_second_run_writes_to_nobody_twice(self) -> None:
        call_command("email_sponsorship_reset", stdout=io.StringIO())
        out = io.StringIO()
        call_command("email_sponsorship_reset", stdout=out)

        self.assertEqual(self.recipients(), ["lost@example.com"])
        self.assertIn("Nobody to write to", out.getvalue())

    def test_a_dry_run_lists_everyone_and_sends_nothing(self) -> None:
        out = io.StringIO()
        call_command("email_sponsorship_reset", "--dry-run", stdout=out)

        self.assertEqual(self.recipients(), [])
        self.assertIn("Would write to 1 people", out.getvalue())
        self.assertIn("lost@example.com", out.getvalue())
