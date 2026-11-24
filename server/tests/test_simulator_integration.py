"""The public tournament simulator: seeded and unseeded Swiss."""

import re
from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.tests.localserver import APP_URL, running_test_server

SEED_LABEL = re.compile(r"\(\d+\)")


@pytest.mark.django_db(transaction=True)
class TestSimulatorIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def set_teams(self, count: int) -> None:
        self.execute_script(
            "const el = document.querySelector('input[type=number]');"
            "const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
            "set.call(el, arguments[0]);"
            "el.dispatchEvent(new Event('input', {bubbles: true}));",
            str(count),
        )

    def generate(self, *, unseeded: bool, teams: int = 12) -> None:
        self.open(f"{APP_URL}/simulations/tournament")
        self.wait_for_element('button:contains("Generate Tournament")', timeout=10)
        self.set_teams(teams)
        self.click('button:contains("Swiss Round")')
        if unseeded:
            self.click('button:contains("Unseeded")')
        self.click('button:contains("Generate Tournament")')
        self.wait_for_text("Swiss Round 1", timeout=10)

    def round_one_text(self) -> str:
        return self.execute_script(
            "const h = [...document.querySelectorAll('h3')]"
            ".find(el => el.textContent.startsWith('Swiss Round 1'));"
            "return h.parentElement.querySelector('.space-y-1\\\\.5').innerText;"
        )

    def test_unseeded_hides_seeds(self) -> None:
        self.generate(unseeded=True)
        self.assert_text("Teams")
        self.assert_text_not_visible("Initial Tournament Seedings")
        self.assertFalse(SEED_LABEL.search(self.round_one_text()))
        names = self.execute_script(
            "return [...document.querySelectorAll('table')[0].querySelectorAll('tbody tr')]"
            ".map(tr => tr.innerText.trim());"
        )
        self.assertEqual(
            [f"Team {n}" for n in range(1, 13)],
            names,
        )
        headers = self.execute_script(
            "return [...document.querySelectorAll('table')[0].querySelectorAll('th')]"
            ".map(th => th.innerText);"
        )
        self.assertEqual(["TEAM"], headers)
        self.assertFalse(
            self.execute_script(
                "return [...document.querySelectorAll('table th')]"
                ".some(th => th.title === 'Tournament seed');"
            )
        )

    def test_seeded_still_shows_seeds(self) -> None:
        self.generate(unseeded=False)
        self.assert_text("Initial Tournament Seedings")
        self.assertTrue(SEED_LABEL.search(self.round_one_text()))

    def test_redraw_changes_round_one(self) -> None:
        self.generate(unseeded=True)
        before = self.round_one_text()
        self.click('button:contains("Redraw")')
        self.wait_for_element("h3", timeout=5)
        self.assertNotEqual(before, self.round_one_text())

    def test_tiebreak_copy_lists_goals_scored(self) -> None:
        self.open(f"{APP_URL}/simulations/tournament")
        self.click('button:contains("Tournament Format")')
        for text in ["Goals scored", "A random lot", "start again from head-to-head"]:
            self.assert_text(text)
