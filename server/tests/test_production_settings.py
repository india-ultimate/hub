import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from hub.redis_auth import password


class TestProductionSettings(SimpleTestCase):
    def load(self, **env: str) -> subprocess.CompletedProcess[str]:
        clean = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "FLY_APP_NAME"}}
        return subprocess.run(
            [sys.executable, "-c", "import hub.production"],
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

    def test_the_public_url_is_configurable_and_feeds_the_mcp_settings(self) -> None:
        script = (
            "import hub.production as s; "
            "print(s.PUBLIC_URL, s.MCP_RESOURCE_URL, "
            "s.OAUTH2_PROVIDER['OIDC_ISS_ENDPOINT'])"
        )
        for env, base in [
            ({}, "https://hub.indiaultimate.org"),
            ({"PUBLIC_URL": "https://staging.example"}, "https://staging.example"),
        ]:
            clean = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "PUBLIC_URL"}}
            result = subprocess.run(  # noqa: S603
                [sys.executable, "-c", script],
                env={**clean, "FLY_APP_NAME": "upai-hub-staging", **env},
                cwd=Path(__file__).parents[2],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(f"{base} {base}/mcp {base}", result.stdout.strip(), result.stderr)

    def test_mcp_is_off_unless_the_environment_turns_it_on(self) -> None:
        for module in ("hub.settings", "hub.production"):
            for env, expected in [({}, "False"), ({"MCP_ENABLED": "1"}, "True")]:
                clean = {k: v for k, v in os.environ.items() if k not in {"MCP_ENABLED"}}
                result = subprocess.run(  # noqa: S603
                    [sys.executable, "-c", f"import {module} as s; print(s.MCP_ENABLED)"],
                    env={**clean, "FLY_APP_NAME": "upai-hub-staging", **env},
                    cwd=Path(__file__).parents[2],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(expected, result.stdout.strip(), (module, env, result.stderr))

    def test_production_counts_its_queries(self) -> None:
        # The plain engine would leave every database metric at zero.
        script = "import hub.production as s; print(s.DATABASES['default']['ENGINE'])"
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            env={
                **os.environ,
                "FLY_APP_NAME": "upai-hub",
                "DATABASE_URL": "postgres://u:p@h:5432/db",
            },
            cwd=Path(__file__).parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            "django_prometheus.db.backends.postgresql", result.stdout.strip(), result.stderr
        )

    def test_production_keeps_its_connections(self) -> None:
        script = (
            "import hub.production as s; d = s.DATABASES['default']; "
            "print(d['CONN_MAX_AGE'], d['CONN_HEALTH_CHECKS'])"
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
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

    def cache(self, **env: str) -> str:
        script = (
            "import hub.production as s; c = s.CACHES['default']; "
            "o = c.get('OPTIONS') or {}; r = o.get('retry'); "
            "print(c['BACKEND'], c.get('LOCATION'), o.get('socket_connect_timeout'), o.get('socket_timeout'), "
            "getattr(r, '_retries', None), [e.__module__ + '.' + e.__name__ for e in o.get('retry_on_error', [])])"
        )
        clean = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "REDIS_HOST"}}
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            env={**clean, **env},
            cwd=Path(__file__).parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or result.stderr

    def test_production_shares_the_workers_redis_and_fails_fast(self) -> None:
        host = "worker.process.upai-hub.internal"
        self.assertEqual(
            "django.core.cache.backends.redis.RedisCache "
            f"redis://:{password('s')}@{host}:6379/0 "
            "0.1 0.2 1 ['redis.exceptions.ConnectionError']",
            self.cache(REDIS_HOST=host, SECRET_KEY="s"),  # noqa: S106
        )

    def test_without_redis_nothing_is_cached(self) -> None:
        self.assertEqual(
            "django.core.cache.backends.dummy.DummyCache None None None None []",
            self.cache(SECRET_KEY="s"),  # noqa: S106
        )

    def test_sentry_traces_a_tenth_of_requests_and_keeps_every_error(self) -> None:
        script = (
            "import hub.production, sentry_sdk; o = sentry_sdk.get_client().options; "
            "print(o['traces_sample_rate'], o['sample_rate'])"
        )
        clean = {k: v for k, v in os.environ.items() if k not in {"DATABASE_URL", "FLY_APP_NAME"}}
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            # A DSN nothing listens at: init sends nothing on its own.
            env={**clean, "SENTRY_DSN": "https://key@sentry.invalid/1"},
            cwd=Path(__file__).parents[2],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual("0.1 1.0", result.stdout.strip(), result.stderr)


class TestRedisPassword(SimpleTestCase):
    def test_it_is_derived_from_the_key(self) -> None:
        self.assertEqual(password("a"), password("a"))
        self.assertNotEqual(password("a"), password("b"))
        self.assertRegex(password("a"), r"^[0-9a-f]{64}$")
        self.assertNotEqual("a", password("a"))
