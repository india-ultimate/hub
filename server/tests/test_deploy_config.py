import importlib.util
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml
from django.test import SimpleTestCase
from django_prometheus.middleware import Metrics
from prometheus_client import REGISTRY

ROOT = Path(__file__).parents[2]
# What a query adds to a metric family's name.
SUFFIXES = ("_total", "_bucket", "_count", "_sum", "")


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

    def test_only_app_machines_serve_and_suspend_when_idle(self) -> None:
        (service,) = load("fly.toml")["services"]
        self.assertEqual(["app"], service["processes"])
        # Resumes in under a second; a stopped machine boots Django again.
        self.assertEqual("suspend", service["auto_stop_machines"])
        self.assertIs(True, service["auto_start_machines"])
        self.assertEqual(1, service["min_machines_running"])

    def test_the_proxy_admits_no_more_than_gunicorn_serves(self) -> None:
        # Past workers x threads, requests queue in gunicorn until they 504.
        config = load("fly.toml")
        slots = int(config["env"]["GUNICORN_WORKERS"]) * int(config["env"]["GUNICORN_THREADS"])
        self.assertLessEqual(config["services"][0]["concurrency"]["soft_limit"], slots)

    def test_each_deploy_keeps_three_app_machines(self) -> None:
        # Fly has no count in fly.toml; the proxy only starts machines that exist.
        workflow = (ROOT / ".github/workflows/deploy.yml").read_text()
        count = re.search(r"flyctl scale count app=(\d+) --yes", workflow)
        if count is None:
            self.fail("deploy.yml doesn't set the app machine count")
        machines = int(count.group(1))
        self.assertEqual(3, machines)
        # Each thread holds a DB connection: keep well inside max_connections 300.
        env = load("fly.toml")["env"]
        threads = int(env["GUNICORN_WORKERS"]) * int(env["GUNICORN_THREADS"])
        self.assertLessEqual(machines * threads, 150)

    def test_gunicorn_survives_a_resume(self) -> None:
        # Before 22.0 the heartbeat used the wall clock, which jumps on resume. On 23,
        # recycling under max-requests drops accepted requests as 502s; 26 serves them first.
        pin = re.search(r"^gunicorn==(\d+)\.", (ROOT / "requirements.txt").read_text(), re.M)
        if pin is None:
            self.fail("requirements.txt doesn't pin gunicorn")
        self.assertGreaterEqual(int(pin.group(1)), 26)

    def test_no_swap_so_machines_can_suspend(self) -> None:
        # Fly can't suspend a machine with swap; it would fall back to a full stop.
        self.assertNotIn("swap_size_mb", load("fly.toml"))

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

    def test_ci_splits_the_browser_tests_across_every_group(self) -> None:
        # Split by .test_durations; a group missing from the matrix never runs.
        workflow = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())
        job = workflow["jobs"]["integration-tests"]
        command = next(s["run"] for s in job["steps"] if "-k Integration" in s.get("run", ""))
        splits = re.search(r"--splits (\d+) --group \$\{\{ matrix\.group \}\}", command)
        if splits is None:
            self.fail("the browser tests aren't split")
        self.assertEqual(
            list(range(1, int(splits.group(1)) + 1)), job["strategy"]["matrix"]["group"]
        )
        self.assertIs(False, job["strategy"]["fail-fast"])

    def test_ci_fits_in_the_free_plan_s_twenty_runners(self) -> None:
        # More would queue, and a queued group finishes last.
        jobs = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())["jobs"]
        groups = len(jobs["integration-tests"]["strategy"]["matrix"]["group"])
        alongside = [name for name in jobs if "needs" not in jobs[name]]
        self.assertGreaterEqual(groups, 15)
        self.assertLessEqual(groups + len(alongside) - 1, 20)

    def test_the_unit_tests_run_on_every_core(self) -> None:
        jobs = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())["jobs"]
        command = next(
            s["run"] for s in jobs["run-django-tests"]["steps"] if "pytest" in s.get("run", "")
        )
        self.assertIn("-n auto", command)

    def test_the_required_check_still_reports(self) -> None:
        # main's branch protection requires "run-integration-tests"; the matrix
        # reports "integration-tests (1)" and so on, so this job answers for all.
        jobs = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())["jobs"]
        gate = jobs["run-integration-tests"]
        self.assertEqual(["integration-tests"], gate["needs"])
        self.assertEqual("always()", gate["if"])
        (step,) = gate["steps"]
        self.assertIn("needs.integration-tests.result", step["run"])

    def test_nginx_takes_a_form_with_two_full_size_files(self) -> None:
        # The college ID and tournament forms send two files, each up to the
        # 10 MB the browser allows; one request over the limit is a bare 413.
        nginx = (ROOT / "deploy/nginx.conf").read_text()
        block = re.search(r"location ~ \^/\(api\|admin\|ckeditor\|media\)/ \{[^}]*\}", nginx)
        if block is None:
            self.fail("no location for the API in nginx.conf")
        limit = re.search(r"client_max_body_size (\d+)M;", block.group(0))
        if limit is None:
            self.fail("the API location sets no client_max_body_size")
        self.assertGreaterEqual(int(limit.group(1)), 2 * 10 + 1)

    def test_ci_tests_on_the_python_the_image_runs(self) -> None:
        image = re.search(r"^FROM python:(\S+)", (ROOT / "Dockerfile").read_text(), re.M)
        if image is None:
            self.fail("Dockerfile has no FROM python:<version>")
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        versions = set(re.findall(r'python-version: "([^"]+)"', workflow))
        self.assertEqual({image.group(1)}, versions)


class TestRedisOnTheWorker(SimpleTestCase):
    def test_the_apps_find_redis_on_the_worker(self) -> None:
        self.assertEqual("worker.process.upai-hub.internal", load("fly.toml")["env"]["REDIS_HOST"])
        # Staging keeps no cache.
        self.assertNotIn("REDIS_HOST", load("fly.staging.toml")["env"])

    def test_the_image_has_redis(self) -> None:
        self.assertRegex(
            (ROOT / "Dockerfile").read_text(), r"apt-get install[^\n]*\bredis-server\b"
        )

    def test_the_worker_starts_redis_before_the_task_queue(self) -> None:
        script = (ROOT / "deploy/start-worker.sh").read_text()
        redis, queue = script.index("redis-server"), script.index("exec python")
        self.assertLess(redis, queue)
        for flag in (
            "--daemonize yes",
            "--requirepass",
            "--maxmemory 64mb",
            "--maxmemory-policy allkeys-lru",
            '--save ""',
            "--appendonly no",
        ):
            self.assertIn(flag, script)

    def test_the_worker_runs_the_queue_even_if_redis_wont_start(self) -> None:
        # The cache is optional and fails open: no failure of it may exit the
        # script (set -e), or no emails go out and no nightly jobs run.
        script = (ROOT / "deploy/start-worker.sh").read_text()
        self.assertRegex(script, r"if PASS=\$\(.*\); then")
        self.assertRegex(script, r"redis-server [^\n]*(\\\n[^\n]*)*\|\|")
        self.assertIn("else", script)

    def test_the_apps_dont_run_redis(self) -> None:
        self.assertNotIn("redis", (ROOT / "deploy/start.sh").read_text())


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
                "for i in $(seq 100); do\n"
                '  grep -qx "sudo nginx" "$LOG" && sleep "${GUNICORN_UP:-0}" && exit 0; sleep 0.1\n'
                "done\n"
                "exit 1"
            ),
        }
        for command, body in stubs.items():
            stub = folder / command
            stub.write_text(f"#!/bin/sh\n{body}\n")
            stub.chmod(0o755)
        self.metrics_dir = folder / "metrics"
        self.metrics_dir.mkdir()
        (self.metrics_dir / "counter_1.db").touch()  # from a previous boot
        self.exit_code = subprocess.run(  # noqa: S603
            ["/bin/bash", str(ROOT / "deploy/start.sh")],
            env={
                "PATH": f"{folder}:/usr/bin:/bin",
                "HOME": str(folder),
                "LOG": str(log),
                "PROMETHEUS_MULTIPROC_DIR": str(self.metrics_dir),
                **env,
            },
            check=False,
        ).returncode
        self.log = log.read_text().splitlines()
        # Started in the background, so its place among the rest isn't fixed.
        lines = [line for line in self.log if line != "python deploy/metrics.py"]
        # gunicorn's and curl's flags aren't the point here.
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

    def test_the_metrics_exporter_comes_back_while_gunicorn_runs(self) -> None:
        # The stub exits at once, as a crashed exporter would.
        self.start(DATABASE_URL="postgres://u:p@h:5432/db", GUNICORN_UP="2.5")
        self.assertGreaterEqual(self.log.count("python deploy/metrics.py"), 2)

    def test_the_metrics_exporter_adds_up_this_boot_s_workers(self) -> None:
        self.start(DATABASE_URL="postgres://u:p@h:5432/db")
        self.assertIn("python deploy/metrics.py", self.log)
        (gunicorn,) = [line for line in self.log if line.startswith("gunicorn ")]
        # Its hook drops a recycled worker's numbers.
        self.assertIn("-c deploy/gunicorn.conf.py", gunicorn)
        # A previous boot's counts would be added to this one's.
        self.assertEqual([], list(self.metrics_dir.iterdir()))


class TestMetrics(SimpleTestCase):
    def test_fly_scrapes_the_exporter_on_app_machines_only(self) -> None:
        config = load("fly.toml")
        self.assertEqual(
            {"port": 9091, "path": "/metrics", "processes": ["app"]}, config["metrics"]
        )
        # Not a service port, so not reachable from the internet.
        for service in config["services"]:
            ports = [service["internal_port"], *(p["port"] for p in service["ports"])]
            self.assertNotIn(9091, ports)

    def test_the_exporter_sums_every_worker(self) -> None:
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(folder)}
        count = "from prometheus_client import Counter; Counter('hub_test', 'test').inc({})"
        for n in (2, 3):  # two worker processes
            worker = [sys.executable, "-c", count.format(n)]
            subprocess.run(worker, env=env, check=True)  # noqa: S603

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        exporter = subprocess.Popen(  # noqa: S603
            [sys.executable, str(ROOT / "deploy/metrics.py")],
            env={**env, "METRICS_PORT": str(port)},
        )
        self.addCleanup(exporter.kill)
        body = ""
        for _ in range(50):
            try:
                with urlopen(f"http://127.0.0.1:{port}/metrics", timeout=1) as response:
                    body = response.read().decode()
                break
            except OSError:
                time.sleep(0.1)
        self.assertIn("hub_test_total 5.0", body)

    def test_the_dashboard_asks_for_metrics_the_app_has(self) -> None:
        # A renamed metric would leave its panel empty without a word.
        dashboard = (ROOT / "deploy/grafana/hub.json").read_text()
        asked = set(re.findall(r"hub_django_\w+", dashboard))
        Metrics.get_instance()  # the request metrics, made on first use
        families = {m.name for m in REGISTRY.collect()}
        missing = {
            name
            for name in asked
            if not any(name.removesuffix(suffix) in families for suffix in SUFFIXES)
        }
        self.assertTrue(asked)
        self.assertEqual(set(), missing)


class TestDurations(SimpleTestCase):
    def test_ci_timings_become_pytest_split_ids(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "update_test_durations", ROOT / "scripts/update-test-durations.py"
        )
        assert spec and spec.loader  # noqa: S101 - narrows the type
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder)
        (folder / "1").mkdir()
        (folder / "1" / "1.xml").write_text(
            "<testsuites><testsuite>"
            '<testcase classname="server.tests.test_ui.TestIntegration" name="test_a" time="12.3456"/>'
            '<testcase classname="server.tests.test_ui.TestIntegration" name="test_b" time="1">'
            "<skipped/></testcase>"
            '<testcase classname="server.tests.test_x" name="test_c" time="2"/>'
            "</testsuite></testsuites>"
        )
        self.assertEqual(
            {
                "server/tests/test_ui.py::TestIntegration::test_a": 12.346,
                "server/tests/test_x.py::test_c": 2.0,
            },
            script.durations(folder),
        )
