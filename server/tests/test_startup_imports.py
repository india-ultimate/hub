"""Every worker imports the whole URL conf, so a module-scope import is paid
by all of them. These assert a package stays out of sys.modules until used."""

import os
import subprocess
import sys

from django.test import SimpleTestCase

URL_CONF_SCRIPT = (
    "import sys, django; django.setup();"
    "from django.urls import get_resolver; get_resolver().url_patterns;"
    "sys.exit(1 if {names!r} & set(sys.modules) else 0)"
)


def _run(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],  # noqa: S603
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "hub.test_settings"},
        capture_output=True,
        text=True,
        check=False,
    )


class TestChatImportCost(SimpleTestCase):
    def test_url_conf_leaves_groq_and_httpx_alone(self) -> None:
        script = URL_CONF_SCRIPT.format(names={"groq", "httpx"})
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)


class TestTournamentAgentImportCost(SimpleTestCase):
    def test_url_conf_leaves_the_opencode_client_alone(self) -> None:
        script = (
            "import sys, django; django.setup();"
            "from django.urls import get_resolver; get_resolver().url_patterns;"
            "sys.exit("
            "1 if 'httpx' in sys.modules "
            "or 'server.tournament_agent.services.agent' in sys.modules "
            "else 0)"
        )
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)


class TestAnnouncementsImportCost(SimpleTestCase):
    def test_setup_leaves_markdownify_alone(self) -> None:
        # markdownify is no longer a dependency; this guards re-adding it at
        # module scope, where django.setup() pays 5.7MB and so does cron.
        script = (
            "import sys, django; django.setup();"
            "sys.exit(1 if {'markdownify', 'bs4'} & set(sys.modules) else 0)"
        )
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)


class TestAuthImportCost(SimpleTestCase):
    def test_url_conf_leaves_jwt_and_cryptography_alone(self) -> None:
        script = URL_CONF_SCRIPT.format(names={"jwt", "cryptography"})
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)
