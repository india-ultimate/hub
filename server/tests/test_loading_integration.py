from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import Team, User
from server.tests import test_ui
from server.tests.base import add_teams_to_event, create_event, create_player, create_tournament
from server.tests.localserver import APP_URL, running_test_server
from server.tournament.models import Tournament

PENDING = "#header-auth-pending"
LOGIN = "#header-login"
TEAMS_LOGIN_TEXT = "Please login to view your teams"

def loading(label: str) -> str:
    return f'//*[@role="status"][.//span[normalize-space()="{label}"]]'


TOURNAMENT_SKELETON = loading("Loading tournament")


@pytest.mark.django_db(transaction=True)
class TestLoadingIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as
    slow_requests = test_ui.TestIntegration.slow_requests

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        self.user = User.objects.create(username="ananya", first_name="Ananya", last_name="Rao")
        create_player(self.user)

    def assert_slowed(self) -> None:
        self.assert_true(self.execute_script("return window.__slowed === true"))

    def test_signed_in_header_never_offers_login(self) -> None:
        self.sign_in_as(self.user)
        self.slow_requests("/api/me", 4000)
        self.open(APP_URL)
        self.assert_slowed()
        self.assert_element(PENDING)
        self.assert_element_not_present(LOGIN)
        self.assert_element("#my-account", timeout=10)
        self.assert_element_not_present(LOGIN)

    def test_teams_page_does_not_ask_a_signed_in_player_to_log_in(self) -> None:
        self.sign_in_as(self.user)
        self.slow_requests("/api/me", 4000)
        self.open(f"{APP_URL}/teams")
        self.assert_slowed()
        self.assert_text("My Teams")
        self.assert_element(PENDING)
        self.assert_text_not_visible(TEAMS_LOGIN_TEXT)
        self.assert_element("#my-account", timeout=10)
        self.assert_text_not_visible(TEAMS_LOGIN_TEXT)

    def test_stale_hint_settles_logged_out(self) -> None:
        self.open(APP_URL)
        self.driver.add_cookie({"name": "hub_auth", "value": "1", "path": "/"})
        self.open(APP_URL)
        self.assert_element(LOGIN, timeout=5)

    def test_failed_me_settles_logged_out(self) -> None:
        self.sign_in_as(self.user)
        self.slow_requests("/api/me", 0, status=500)
        self.open(APP_URL)
        self.assert_slowed()
        self.assert_element(LOGIN, timeout=5)
        self.assert_element_not_present(PENDING)

    def make_tournament(self) -> Tournament:
        event = create_event("Loading Open")
        add_teams_to_event(event, 2)
        return create_tournament(event)

    def test_tournament_page_shows_a_skeleton_not_placeholders(self) -> None:
        tournament = self.make_tournament()
        self.slow_requests("/api/tournament", 4000)
        self.open(f"{APP_URL}/tournament/{tournament.event.slug}")
        self.assert_slowed()
        self.assert_element(TOURNAMENT_SKELETON)
        self.assert_not_in("Invalid Date", self.get_page_source())
        self.assert_element_not_present('a[href*="undefined"]')
        self.assert_text("Loading Open", timeout=10)
        self.assert_element_not_present(TOURNAMENT_SKELETON)

    def test_unknown_tournament_still_says_not_found(self) -> None:
        self.open(f"{APP_URL}/tournament/no-such-slug")
        self.assert_text("Tournament could not be fetched", timeout=10)
        self.assert_element_not_present(TOURNAMENT_SKELETON)

    def test_leaderboard_does_not_say_no_players_while_loading(self) -> None:
        tournament = self.make_tournament()
        self.slow_requests("/leaderboard", 4000)
        self.open(f"{APP_URL}/tournament/{tournament.event.slug}/leaderboard")
        self.assert_slowed()
        self.assert_element(loading("Loading leaderboard"))
        self.assert_text_not_visible("No Players To Show")
        self.assert_text("No Players To Show", timeout=10)

    def test_team_points_badge_settles_when_the_points_query_is_off(self) -> None:
        tournament = self.make_tournament()
        team = tournament.teams.get(name="Team 1")
        self.open(f"{APP_URL}/tournament/{tournament.event.slug}/team/{team.slug}")
        self.assert_text("Team 1", timeout=10)
        self.assert_text("Points")
        self.sleep(2)
        self.assert_element_not_present(".inline-block.h-4.w-8")

    def test_team_points_badge_shows_no_zero_while_the_tournament_loads(self) -> None:
        tournament = self.make_tournament()
        team = tournament.teams.get(name="Team 1")
        self.slow_requests("/api/tournament", 4000)
        self.open(f"{APP_URL}/tournament/{tournament.event.slug}/team/{team.slug}")
        self.assert_slowed()
        self.assert_text("Team 1", timeout=10)
        self.assert_element(".inline-block.h-4.w-8")
        self.assert_not_in("0", self.get_text("p.bg-blue-100"))

    def test_team_page_shows_a_skeleton_not_dashes(self) -> None:
        Team.objects.create(name="Loading Lions", slug="loading-lions")
        self.slow_requests("/api/team-profile/loading-lions", 4000)
        self.open(f"{APP_URL}/team/loading-lions")
        self.assert_slowed()
        self.assert_element(loading("Loading team"))
        self.assert_element_not_present("img:not([src])")
        self.assert_text("Loading Lions", timeout=10)
        self.assert_element_not_present(loading("Loading team"))
