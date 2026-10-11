import json
import re
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

    def test_gunicorn_survives_a_resume(self) -> None:
        # Before 22.0 the heartbeat used the wall clock, which jumps on resume.
        pin = re.search(r"^gunicorn==(\d+)\.", (ROOT / "requirements.txt").read_text(), re.M)
        if pin is None:
            self.fail("requirements.txt doesn't pin gunicorn")
        self.assertGreaterEqual(int(pin.group(1)), 22)

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
                # Fly sends the machine's IP, which Debian's default site would answer.
                self.assertIn(check["headers"]["Host"], server_names)

    def test_nginx_answers_the_health_check_itself(self) -> None:
        # Or the check waits behind gunicorn's busy threads, and a busy machine
        # is taken out of rotation just when it's needed.
        nginx = (ROOT / "deploy/nginx.conf").read_text()
        self.assertRegex(nginx, r"location = /api/health \{[^}]*return 200")

    def test_the_worker_always_restarts(self) -> None:
        # Fly's default gives up after 10 failures, e.g. a long Postgres outage,
        # and then no emails go out and no nightly jobs run.
        restarts = {tuple(r["processes"]): r["policy"] for r in load("fly.toml")["restart"]}
        self.assertEqual({("worker",): "always"}, restarts)

    def test_ci_tests_on_the_python_the_image_runs(self) -> None:
        image = re.search(r"^FROM python:(\S+)", (ROOT / "Dockerfile").read_text(), re.M)
        if image is None:
            self.fail("Dockerfile has no FROM python:<version>")
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        versions = set(re.findall(r'python-version: "([^"]+)"', workflow))
        self.assertEqual({image.group(1)}, versions)


class TestAppStart(SimpleTestCase):
    def start(self, sudo: str = "", **env: str) -> list[str]:
        """What deploy/start.sh runs, in order, with sudo, python and gunicorn stubbed.

        `sudo` is extra shell run first in the sudo stub, e.g. to fail a command.
        """
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        log = folder / "log"
        stubs = {
            "sudo": f'{sudo}\necho "sudo $*" >> "$LOG"',
            "python": 'echo "python $*" >> "$LOG"',
            # Answers only once gunicorn is up, as the real one would.
            "curl": 'grep -q "^gunicorn" "$LOG" || exit 7\necho "curl $*" >> "$LOG"',
            # Runs until nginx is started, so the script's waiting is exercised.
            "gunicorn": (
                'echo "gunicorn $*" >> "$LOG"\n'
                'for i in $(seq 100); do grep -qx "sudo nginx" "$LOG" && exit 0; sleep 0.1; done\n'
                "exit 1"
            ),
        }
        for command, body in stubs.items():
            stub = folder / command
            stub.write_text(f"#!/bin/sh\n{body}\n")
            stub.chmod(0o755)
        self.exit_code = subprocess.run(
            ["/bin/bash", str(ROOT / "deploy/start.sh")],  # noqa: S603
            env={"PATH": f"{folder}:/usr/bin:/bin", "HOME": str(folder), "LOG": str(log), **env},
            check=False,
        ).returncode
        # gunicorn's and curl's flags aren't the point here.
        lines = log.read_text().splitlines()
        flagged = ("gunicorn ", "curl ")
        return [line.split(" ")[0] if line.startswith(flagged) else line for line in lines]

    def test_nginx_takes_traffic_only_once_gunicorn_answers(self) -> None:
        # A machine the proxy just started would otherwise answer 502 meanwhile.
        self.assertEqual(
            [
                "python manage.py check --deploy",
                "sudo nginx -t",
                "gunicorn",
                "curl",
                "sudo nginx",
            ],
            self.start(DATABASE_URL="postgres://u:p@h:5432/db"),
        )
        self.assertEqual(0, self.exit_code)

    def test_a_bad_nginx_config_fails_the_boot(self) -> None:
        # A non-zero exit restarts the machine; gunicorn stopped later exits 0
        # and leaves it stopped.
        fail_check = '[ "$*" = "nginx -t" ] && exit 1'
        lines = self.start(sudo=fail_check, DATABASE_URL="postgres://u:p@h:5432/db")
        self.assertEqual(["python manage.py check --deploy"], lines)
        self.assertNotEqual(0, self.exit_code)

    def test_a_machine_with_its_own_sqlite_migrates_at_boot(self) -> None:
        self.assertEqual(
            [
                "python manage.py migrate",
                "python manage.py check --deploy",
                "sudo nginx -t",
                "gunicorn",
                "curl",
                "sudo nginx",
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
