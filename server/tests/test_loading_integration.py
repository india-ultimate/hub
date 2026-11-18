from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import User
from server.tests import test_ui
from server.tests.base import create_player
from server.tests.localserver import APP_URL, running_test_server

PENDING = "#header-auth-pending"
LOGIN = "#header-login"
TEAMS_LOGIN_TEXT = "Please login to view your teams"


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
