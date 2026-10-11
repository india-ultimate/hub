import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class TestProductionSettings(SimpleTestCase):
    def load(self, **env: str) -> subprocess.CompletedProcess[str]:
        clean = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "FLY_APP_NAME"}}
        return subprocess.run(
            [sys.executable, "-c", "import hub.production"],  # noqa: S603
            env={**clean, **env},
            cwd=Path(__file__).parents[2],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_wont_start_without_its_database(self) -> None:
        # The machines' disk doesn't last: a SQLite fallback would lose every write.
        result = self.load(FLY_APP_NAME="upai-hub")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("DATABASE_URL", result.stderr)

    def test_production_starts_with_its_database(self) -> None:
        result = self.load(FLY_APP_NAME="upai-hub", DATABASE_URL="postgres://u:p@h:5432/db")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_staging_runs_on_sqlite(self) -> None:
        self.assertEqual(0, self.load(FLY_APP_NAME="upai-hub-staging").returncode)

    def test_production_keeps_its_connections(self) -> None:
        script = (
            "import hub.production as s; d = s.DATABASES['default']; "
            "print(d['CONN_MAX_AGE'], d['CONN_HEALTH_CHECKS'])"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],  # noqa: S603
            env={
                **{k: v for k, v in os.environ.items() if k != "FLY_APP_NAME"},
                "FLY_APP_NAME": "upai-hub",
                "DATABASE_URL": "postgres://u:p@h:5432/db",
            },
            cwd=Path(__file__).parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual("60 True", result.stdout.strip(), result.stderr)
