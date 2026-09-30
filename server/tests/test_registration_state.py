"""A team's registration for one tournament: what's done, what's blocked, why."""

from django.db import IntegrityError
from django.test import TestCase

from server.core.models import Team
from server.registration.models import RosterEntry
from server.tests.test_payment_accounts import open_event
from server.tests.test_subscription_model import make_player


class TestRosterEntry(TestCase):
    def test_one_entry_per_player_per_team_per_event(self) -> None:
        event, team, player = open_event(), Team.objects.create(name="T"), make_player("a@x.com")
        RosterEntry.objects.create(event=event, team=team, player=player)
        with self.assertRaises(IntegrityError):
            RosterEntry.objects.create(event=event, team=team, player=player)
