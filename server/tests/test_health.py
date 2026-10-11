from django.test import Client, TestCase


class TestHealth(TestCase):
    def test_health_answers_without_login_or_the_database(self) -> None:
        # Fly's check: a DB query here would fail every machine in a Postgres blip.
        with self.assertNumQueries(0):
            response = Client().get("/api/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())
