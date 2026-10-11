from pathlib import Path

import tomllib
from django.test import Client, TestCase, override_settings

ROOT = Path(__file__).parents[2]


class TestHealth(TestCase):
    def test_health_answers_without_login_or_the_database(self) -> None:
        # Fly's check: a DB query here would fail every machine in a Postgres blip.
        with self.assertNumQueries(0):
            response = Client().get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_answers_fly_s_check(self) -> None:
        # As Fly sends it: gunicorn turns X-Forwarded-Proto from nginx into https.
        with (ROOT / "fly.toml").open("rb") as f:
            (check,) = tomllib.load(f)["services"][0]["http_checks"]
        response = Client().get(check["path"], HTTP_HOST=check["headers"]["Host"], secure=True)
        self.assertEqual(200, response.status_code)
