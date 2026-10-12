"""The rules page renders markdown that admins (and the chat's LLM) write, so a
link in it must never run script."""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.tests.localserver import APP_URL, running_test_server
from server.tests.test_payment_accounts import open_event
from server.tournament.models import Tournament

RULES = """
# Rules

[js](javascript:alert(1))

<javascript:alert(2)>

[page](data:text/html,<script>alert(3)</script>)

[vb](vbscript:msgbox(4))

![img](javascript:alert(5))

[web](https://example.com/rules)

[mail](mailto:director@example.com)

[phone](tel:+911234567890)

[relative](/tournaments)

[anchor](#format)
"""

DANGEROUS = (
    'a[href^="javascript:"], a[href^="data:"], a[href^="vbscript:"], img[src^="javascript:"]'
)

SAFE = (
    "https://example.com/rules",
    "mailto:director@example.com",
    "tel:+911234567890",
    "/tournaments",
    "#format",
)


@pytest.mark.django_db(transaction=True)
class TestTournamentRulesIntegration(BaseCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def test_dangerous_links_in_the_rules_are_not_live(self) -> None:
        event = open_event(title="Nationals", type="OPN")
        Tournament.objects.create(event=event, status=Tournament.Status.SCHEDULING, rules=RULES)

        self.open(f"{APP_URL}/tournament/{event.slug}/rules")
        self.assert_element('a[href="https://example.com/rules"]')

        hrefs = self.execute_script(
            "return Array.from(document.querySelectorAll('a')).map(a => a.getAttribute('href'))"
        )
        dangerous = self.execute_script(f"return document.querySelectorAll('{DANGEROUS}').length")
        self.assertEqual(0, dangerous, hrefs)
        for safe in SAFE:
            self.assertIn(safe, hrefs)
