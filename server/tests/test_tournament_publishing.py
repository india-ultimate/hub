"""A draft tournament is listed once its team registration has opened."""

import datetime
import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from server.core.models import User
from server.tests.test_tournament_cards import tournament
from server.tournament.models import Tournament
from server.utils import today

DAY = datetime.timedelta(days=1)


class TestOpenRegistrations(TestCase):
    def draft(self, slug: str, opens: datetime.date) -> Tournament:
        t = tournament(slug, opens + 9 * DAY, status=Tournament.Status.DRAFT)
        t.event.team_registration_start_date = opens
        t.event.save()
        return t

    def test_drafts_whose_registration_has_opened_are_listed(self) -> None:
        # Yesterday's covers dates edited in admin after the day's run, or a missed run.
        drafts = [self.draft(s, today() + d) for s, d in (("old", -DAY), ("now", 0 * DAY))]
        later = self.draft("later", today() + DAY)
        live = tournament("live", today(), status=Tournament.Status.LIVE)

        out = StringIO()
        call_command("open_or_close_tournament_registrations", stdout=out)

        for t in [*drafts, later, live]:
            t.refresh_from_db()
        self.assertEqual(["SCH", "SCH"], [t.status for t in drafts])
        self.assertEqual("DFT", later.status)
        self.assertEqual("LIV", live.status)
        self.assertEqual(
            "".join(f"Listing {t.event.title} ({t.pk})\n" for t in drafts), out.getvalue()
        )

    def test_a_tournament_created_after_registration_opened_is_listed(self) -> None:
        self.client.force_login(User.objects.create(username="staff", is_staff=True))

        def create(title: str, opens: datetime.date) -> str:
            day = lambda d: (opens + d * DAY).isoformat()  # noqa: E731
            details = {
                "title": title,
                "start_date": day(9),
                "end_date": day(9),
                "team_registration_start_date": day(0),
                "team_registration_end_date": day(2),
                "player_registration_start_date": day(3),
                "player_registration_end_date": day(4),
                "team_partial_registration_end_date": day(1),
                "team_late_penalty_end_date": day(2),
                "player_late_penalty_end_date": day(4),
                "location": "Pune",
                "type": "MXD",
                "team_fee": 0,
                "player_fee": 0,
                "partial_team_fee": 0,
                "team_late_penalty": 0,
                "player_late_penalty": 0,
                "is_iu_sanctioned": True,
                "age": "Open",
                "surface": "Grass",
                "level": "College",
                "stage": "Regionals",
                "format": "7v7",
                "is_subscription_needed": False,
            }
            response = self.client.post(
                "/api/tournaments", {"tournament_details": json.dumps(details)}
            )
            self.assertEqual(200, response.status_code, response.content)
            return str(response.json()["status"])

        self.assertEqual(
            ["SCH", "SCH", "DFT"],
            [create(t, today() + d * DAY) for t, d in (("Old", -1), ("Now", 0), ("Later", 1))],
        )
