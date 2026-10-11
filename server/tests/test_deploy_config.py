import json
import shutil
import subprocess
import sys
import tempfile
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


class TestApplyProfile(SimpleTestCase):
    def apply(
        self, profile: str, fly_toml: str = "fly.toml"
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        copy = folder / "fly.toml"
        shutil.copy(ROOT / fly_toml, copy)
        script = str(ROOT / "scripts/apply-profile.py")
        result = subprocess.run(
            [sys.executable, script, profile, "--fly-toml", str(copy)],  # noqa: S603
            capture_output=True,
            text=True,
            check=False,
        )
        return result, copy

    def test_each_profile_sizes_the_app_and_leaves_the_worker(self) -> None:
        profiles = json.loads((ROOT / "deploy/profiles.json").read_text())
        for name, profile in profiles.items():
            with self.subTest(profile=name):
                result, copy = self.apply(name)
                self.assertEqual(0, result.returncode, result.stderr)
                with copy.open("rb") as f:
                    config = tomllib.load(f)
                vms = {tuple(vm["processes"]): vm for vm in config["vm"]}
                app = vms[("app",)]
                self.assertEqual(
                    (profile["cpu_kind"], profile["cpus"], profile["memory"]),
                    (app["cpu_kind"], app["cpus"], app["memory"]),
                )
                self.assertEqual(
                    {"processes": ["worker"], "cpu_kind": "shared", "cpus": 1, "memory": "1gb"},
                    vms[("worker",)],
                )
                self.assertEqual(str(profile["workers"]), config["env"]["GUNICORN_WORKERS"])
                limits = config["services"][0]["concurrency"]
                self.assertEqual(profile["soft_limit"], limits["soft_limit"])

    def test_baseline_is_what_fly_toml_already_says(self) -> None:
        result, copy = self.apply("baseline")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual((ROOT / "fly.toml").read_text(), copy.read_text())

    def test_a_config_without_an_app_vm_is_refused(self) -> None:
        result, _ = self.apply("baseline", fly_toml="fly.staging.toml")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("app", result.stderr)
