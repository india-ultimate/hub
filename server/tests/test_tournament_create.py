import json
from typing import Any

from django.core.exceptions import ValidationError

from server.series.models import Series
from server.tests.base import TOURNAMENT_DETAILS, ApiBaseTestCase, create_event
from server.tournament.models import Event


class TournamentCreateTests(ApiBaseTestCase):
    def create(self, **overrides: Any) -> Any:
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        details = {**TOURNAMENT_DETAILS, **overrides}
        return self.client.post(
            "/api/tournaments", data={"tournament_details": json.dumps(details)}
        )

    def test_create_saves_tags(self) -> None:
        response = self.create(skill_division="Elite")
        self.assertEqual(200, response.status_code, response.content)
        event = Event.objects.get(title="Tagged Cup")
        self.assertEqual(
            (True, "Masters", "Beach", "Club", "Nationals", "5v5", "Elite", False),
            tuple(getattr(event, field) for field in Event.TAG_FIELDS),
        )

    def test_create_saves_membership(self) -> None:
        response = self.create(is_subscription_needed=True)
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(Event.objects.get(title="Tagged Cup").is_subscription_needed)

    def test_create_saves_the_non_player_fee(self) -> None:
        response = self.create(non_player_fee=30000)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(30000, Event.objects.get(title="Tagged Cup").non_player_fee)

    def test_non_players_pay_the_player_fee_unless_told(self) -> None:
        response = self.create()
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(Event.objects.get(title="Tagged Cup").non_player_fee)

    def test_late_and_partial_dates_can_be_left_out(self) -> None:
        # Blank falls back to the regular end date everywhere it's read.
        details = {
            k: v
            for k, v in TOURNAMENT_DETAILS.items()
            if k
            not in (
                "team_partial_registration_end_date",
                "team_late_penalty_end_date",
                "player_late_penalty_end_date",
            )
        }
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/tournaments", data={"tournament_details": json.dumps(details)}
        )
        self.assertEqual(200, response.status_code, response.content)
        event = Event.objects.get(title="Tagged Cup")
        self.assertIsNone(event.player_late_penalty_end_date)
        self.assertEqual(event.player_registration_end_date, event.last_rostering_day())

    def test_a_cleared_late_date_is_left_blank(self) -> None:
        response = self.create(
            player_late_penalty_end_date="", team_partial_registration_end_date=""
        )
        self.assertEqual(200, response.status_code, response.content)
        event = Event.objects.get(title="Tagged Cup")
        self.assertIsNone(event.player_late_penalty_end_date)
        self.assertIsNone(event.team_partial_registration_end_date)

    def test_a_malformed_date_is_refused_not_a_crash(self) -> None:
        response = self.create(player_registration_end_date="20/11/2026")
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn("YYYY-MM-DD", response.json()["message"])

    def test_membership_needs_sanctioned(self) -> None:
        response = self.create(is_subscription_needed=True, is_iu_sanctioned=False)
        self.assertEqual(400, response.status_code)
        self.assertEqual(Event.SANCTION_RULE, response.json()["message"])
        self.assertFalse(Event.objects.filter(title="Tagged Cup").exists())

    def test_create_rejects_unknown_tag(self) -> None:
        response = self.create(surface="Moon")
        self.assertEqual(422, response.status_code)
        self.assertFalse(Event.objects.filter(title="Tagged Cup").exists())


class EventCleanTests(ApiBaseTestCase):
    def test_a_series_event_must_be_sanctioned(self) -> None:
        event = create_event("Series Cup")
        event.series = Series.objects.create(
            name="NCS",
            start_date=event.start_date,
            end_date=event.end_date,
            type="MXD",
            category="Club",
            series_roster_max_players=30,
            event_min_players_male=0,
            event_min_players_female=0,
            event_max_players_male=30,
            event_max_players_female=30,
        )
        with self.assertRaises(ValidationError) as caught:
            event.clean()
        self.assertEqual([Event.SANCTION_RULE], caught.exception.message_dict["is_iu_sanctioned"])
        event.is_iu_sanctioned = True
        event.clean()
