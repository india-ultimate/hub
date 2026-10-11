import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import tomllib
from django.conf import settings
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

    def test_production_migrates_on_release(self) -> None:
        self.assertEqual("python manage.py migrate", load("fly.toml")["deploy"]["release_command"])

    def test_staging_migrates_at_boot_not_on_release(self) -> None:
        # Its SQLite lives in the machine: a release machine's copy is thrown away.
        self.assertNotIn("deploy", load("fly.staging.toml"))

    def test_both_apps_check_health_over_http_as_a_known_host(self) -> None:
        server_names = re.findall(r"server_name ([^;]+);", (ROOT / "deploy/nginx.conf").read_text())
        for name in ("fly.toml", "fly.staging.toml"):
            with self.subTest(name=name):
                (service,) = load(name)["services"]
                self.assertNotIn("tcp_checks", service)
                (check,) = service["http_checks"]
                self.assertEqual("/api/health", check["path"])
                # Or SECURE_SSL_REDIRECT answers Fly's plain-HTTP check with a 301.
                self.assertEqual("https", check["headers"]["X-Forwarded-Proto"])
                # Fly sends the machine's IP: nginx and ALLOWED_HOSTS would refuse it.
                host = check["headers"]["Host"]
                self.assertIn(host, server_names)
                self.assertIn(host, settings.ALLOWED_HOSTS)


class TestAppStart(SimpleTestCase):
    def start(self, **env: str) -> list[str]:
        """What deploy/start.sh runs, in order, with sudo, python and gunicorn stubbed."""
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        log = folder / "log"
        for command in ("sudo", "python", "gunicorn"):
            stub = folder / command
            stub.write_text(f'#!/bin/sh\necho "{command} $*" >> "$LOG"\n')
            stub.chmod(0o755)
        subprocess.run(
            ["/bin/bash", str(ROOT / "deploy/start.sh")],  # noqa: S603
            env={"PATH": f"{folder}:/usr/bin:/bin", "HOME": str(folder), "LOG": str(log), **env},
            check=True,
        )
        # gunicorn's flags aren't the point here.
        lines = log.read_text().splitlines()
        return ["gunicorn" if line.startswith("gunicorn ") else line for line in lines]

    def test_nginx_takes_traffic_only_once_django_has_loaded(self) -> None:
        # A machine the proxy just started would otherwise answer 502 meanwhile.
        self.assertEqual(
            ["python manage.py check --deploy", "sudo nginx", "gunicorn"],
            self.start(DATABASE_URL="postgres://u:p@h:5432/db"),
        )

    def test_a_machine_with_its_own_sqlite_migrates_at_boot(self) -> None:
        self.assertEqual(
            [
                "python manage.py migrate",
                "python manage.py check --deploy",
                "sudo nginx",
                "gunicorn",
            ],
            self.start(),
        )


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
