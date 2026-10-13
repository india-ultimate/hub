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
