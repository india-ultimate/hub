from pathlib import Path
from typing import Any

import tomllib
from django.test import SimpleTestCase

ROOT = Path(__file__).parents[2]


def load(name: str) -> dict[str, Any]:
    with (ROOT / name).open("rb") as f:
        return tomllib.load(f)


class TestFlyConfig(SimpleTestCase):
    def test_app_and_worker_run_apart(self) -> None:
        config = load("fly.toml")
        self.assertEqual(
            {"app": "deploy/start.sh", "worker": "deploy/start-worker.sh"}, config["processes"]
        )
        vms = {tuple(vm["processes"]): vm for vm in config["vm"]}
        size = ("cpu_kind", "cpus", "memory")
        self.assertEqual(("shared", 2, "1gb"), tuple(vms[("app",)][k] for k in size))
        self.assertEqual(("shared", 1, "1gb"), tuple(vms[("worker",)][k] for k in size))

    def test_only_app_machines_serve_and_stop_when_idle(self) -> None:
        (service,) = load("fly.toml")["services"]
        self.assertEqual(["app"], service["processes"])
        self.assertEqual("stop", service["auto_stop_machines"])
        self.assertIs(True, service["auto_start_machines"])
        self.assertEqual(1, service["min_machines_running"])

    def test_both_apps_migrate_on_release_and_check_health_over_http(self) -> None:
        for name in ("fly.toml", "fly.staging.toml"):
            with self.subTest(name=name):
                config = load(name)
                self.assertEqual("python manage.py migrate", config["deploy"]["release_command"])
                (service,) = config["services"]
                self.assertNotIn("tcp_checks", service)
                (check,) = service["http_checks"]
                self.assertEqual("/api/health", check["path"])
                # Or SECURE_SSL_REDIRECT answers Fly's plain-HTTP check with a 301.
                self.assertEqual("https", check["headers"]["X-Forwarded-Proto"])
