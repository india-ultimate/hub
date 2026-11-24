"""A director chooses seeded or unseeded in the manager, and redraws."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Tournament

NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
ROWS = "table tbody tr"


@pytest.mark.django_db(transaction=True)
class TestTournamentSeedingIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def open_manager(self, status: str = Tournament.Status.SCHEDULING) -> Tournament:
        tournament = Tournament.objects.create(
            event=open_event(title="Nationals", type="OPN"), status=status
        )
        teams = [Team.objects.create(name=name) for name in NAMES]
        tournament.teams.set(teams)
        tournament.initial_seeding = {str(i + 1): team.id for i, team in enumerate(teams)}
        tournament.save()
        staff = User.objects.create_user(
            "staff@example.com", "staff@example.com", "pw", is_staff=True
        )
        self.sign_in_as(staff)
        self.open(f"{APP_URL}/tournament-manager")
        self.select_option_by_text("select#tournaments", "Nationals")
        self.wait_for_text("Seeding")
        return tournament

    def drawn_names(self, tournament: Tournament) -> list[str]:
        tournament.refresh_from_db()
        by_id = {team.id: team.name for team in tournament.teams.all()}
        seeding = tournament.initial_seeding
        return [by_id[seeding[str(i + 1)]] for i in range(len(seeding))]

    def shown_names(self) -> list[str]:
        self.wait_for_element(ROWS)
        return [
            self.get_text(f"{ROWS}:nth-child({i + 1}) td")
            for i in range(len(self.find_elements(ROWS)))
        ]

    def test_switch_to_unseeded_shows_draw_and_redraw(self) -> None:
        tournament = self.open_manager()
        self.assert_element("#seeding-seeded[aria-pressed='true']")
        self.assert_element('button:contains("Update Seeding")')
        self.assert_element_not_visible("#seeding-redraw")

        self.click("#seeding-unseeded")
        self.click("#seeding-confirm")
        self.wait_for_element("#seeding-unseeded[aria-pressed='true']")
        self.wait_for_element("#seeding-redraw")
        self.assert_element_not_visible('button:contains("Update Seeding")')
        self.assert_text("DRAW ORDER")
        self.assert_text("Seeds are hidden from the public until a result is in.")

        tournament.refresh_from_db()
        self.assertFalse(tournament.seeded)
        self.assertEqual(self.drawn_names(tournament), self.shown_names())

    def test_confirm_required_before_draw(self) -> None:
        tournament = self.open_manager()
        self.click("#seeding-unseeded")
        self.assert_text("Replaces the current order with a random draw")
        self.assert_element('[role="group"][aria-label="Confirm draw"]')
        self.assert_element("#seeding-unseeded.ring-yellow-400")
        self.assert_text("Switch and draw", "#seeding-confirm")
        tournament.refresh_from_db()
        self.assertTrue(tournament.seeded)

        self.click("#seeding-cancel")
        self.assert_text_not_visible("Replaces the current order with a random draw")
        self.assert_element("#seeding-seeded[aria-pressed='true']")
        tournament.refresh_from_db()
        self.assertTrue(tournament.seeded)
        self.assertEqual(NAMES, self.drawn_names(tournament))

    def test_redraw_updates_list(self) -> None:
        tournament = self.open_manager()
        self.click("#seeding-unseeded")
        self.click("#seeding-confirm")
        self.wait_for_element("#seeding-redraw")

        self.click("#seeding-redraw")
        self.click("#seeding-confirm")
        self.wait_for_element_not_visible("#seeding-confirm")
        after = self.drawn_names(tournament)
        self.assertEqual(sorted(NAMES), sorted(after))
        self.assertEqual(after, self.shown_names())

    def test_controls_disabled_when_live(self) -> None:
        self.open_manager(Tournament.Status.LIVE)
        self.assert_element("#seeding-seeded[disabled][aria-describedby='seeding-locked']")
        self.assert_element("#seeding-unseeded[disabled]")
        self.assert_text("Seeding is locked once the tournament is live.")
