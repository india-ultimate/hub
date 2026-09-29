"""Every gunicorn worker imports the whole URL conf (there is no --preload), so a
module-scope import in any router or model file is paid by every worker, the
tmux'd task worker, and every cron run. These subprocess checks are the same
shape as `server/tests/test_receipts_render.py::TestImportCost`: they do the
real startup work and assert a package never lands in `sys.modules` unless
something actually used it.
"""

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
        """groq drags in httpx, httpcore, anyio, trio and rich - ~11MB and 70+
        modules that only a chat endpoint needs, plus another 6.4MB of httpx
        that the tournament agent would otherwise pull in regardless."""
        script = URL_CONF_SCRIPT.format(names={"groq", "httpx"})
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)


class TestTournamentAgentImportCost(SimpleTestCase):
    def test_url_conf_leaves_the_opencode_client_alone(self) -> None:
        """Only an agent turn needs the OpenCode client, and so httpx."""
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
        """markdownify pulls in bs4, lxml, soupsieve and html5lib - 5.7MB paid
        during django.setup() itself, so the task worker and every cron run
        pay it too, not just a web worker building its URL conf."""
        script = (
            "import sys, django; django.setup();"
            "sys.exit(1 if {'markdownify', 'bs4'} & set(sys.modules) else 0)"
        )
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)


class TestAuthImportCost(SimpleTestCase):
    def test_url_conf_leaves_jwt_and_cryptography_alone(self) -> None:
        """jwt is the only importer of cryptography (32 modules) in the
        process, so a token is made without either until one actually is."""
        script = URL_CONF_SCRIPT.format(names={"jwt", "cryptography"})
        answer = _run(script)
        self.assertEqual(answer.returncode, 0, answer.stderr)
