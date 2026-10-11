from django.test import Client, TestCase, override_settings


class TestHealth(TestCase):
    def test_health_answers_without_login_or_the_database(self) -> None:
        # Fly's check: a DB query here would fail every machine in a Postgres blip.
        with self.assertNumQueries(0):
            response = Client().get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_health_answers_start_sh_s_readiness_check(self) -> None:
        # curl to 127.0.0.1:8000 with X-Forwarded-Proto: https, which gunicorn
        # trusts from 127.0.0.1 and turns into an https request.
        response = Client().get("/api/health", HTTP_HOST="127.0.0.1", secure=True)
        self.assertEqual(200, response.status_code)
