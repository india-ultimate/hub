import atexit
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import django
import requests

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
FRONTEND_DIR = ROOT / "frontend"
# A cold webpack compile alone can take over 30 s, and it happens once a run.
MAX_SERVER_WAIT = 120
PORT = 9981
WEBPACK_SERVER_PORT = 9982
HTTP_SUCCESS = 200

DJANGO_URL = f"http://localhost:{PORT}"
APP_URL = f"http://localhost:{WEBPACK_SERVER_PORT}"


def set_up_django() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "hub.test_settings"
    os.environ["WEBPACK_SERVER_PORT"] = str(WEBPACK_SERVER_PORT)
    django.setup()
    os.environ["PYTHONUNBUFFERED"] = "y"


def assert_server_running(server: "subprocess.Popen[bytes]", log_file: str | None) -> None:
    """Get the exit code of the server, or None if it is still running."""
    if server.poll() is not None:
        message = "Server died unexpectedly!"
        if log_file:
            message += f"\nSee {log_file}\n"
        raise RuntimeError(message)


def server_is_up(server: "subprocess.Popen[bytes]", base_url: str, log_file: str | None) -> bool:
    assert_server_running(server, log_file)
    try:
        response = requests.get(base_url, timeout=2)
        return response.status_code == HTTP_SUCCESS
    except requests.RequestException:
        return False


def wait_server_start(
    server: "subprocess.Popen[bytes]",
    base_url: str,
    log_file: str | None = None,
    dots: bool = False,
) -> None:
    # Wait for the server to start up.
    print(end="\nWaiting for test server (may take a while)")
    if not dots:
        print("\n", flush=True)
    t = time.time()
    while not server_is_up(server, base_url, log_file):
        if dots:
            print(end=".", flush=True)
        time.sleep(0.4)
        if time.time() - t > MAX_SERVER_WAIT:
            raise Exception("Timeout waiting for server")

    print("\n\n--- SERVER IS UP! ---\n", flush=True)


# Started once per test run and shared by every class: starting them, the
# webpack compile above all, was most of each class's time.
_servers: "list[subprocess.Popen[bytes]] | None" = None


def _start_servers(log_file: str | None, dots: bool) -> "list[subprocess.Popen[bytes]]":
    log = sys.stdout
    set_up_django()
    # Series invites are emailed with a signed link; the server needs a key.
    os.environ.setdefault("EMAIL_SECRET_KEY", "test-invite-key")

    django_server = subprocess.Popen(
        ["./manage.py", "runserver", str(PORT)], stdout=log, stderr=log, cwd=ROOT  # noqa: S603
    )
    webpack_command = [
        str(FRONTEND_DIR / "node_modules/.bin/webpack-dev-server"),
        "--config",
        str(HERE / "tests.webpack.config.js"),
        "--mode",
        "development",
    ]
    webpack_server = subprocess.Popen(
        webpack_command, stdout=log, stderr=log, cwd=FRONTEND_DIR  # noqa: S603
    )
    servers = [webpack_server, django_server]
    try:
        wait_server_start(django_server, f"{DJANGO_URL}/api/docs", log_file, dots)
        wait_server_start(webpack_server, APP_URL, log_file, dots)
    except BaseException:
        _stop_servers(servers)  # or they keep their ports for the next run
        raise
    return servers


def _stop_servers(servers: "list[subprocess.Popen[bytes]]") -> None:
    for server in servers:
        server.terminate()
    for server in servers:
        server.wait()


@contextmanager
def running_test_server(
    log_file: str | None = None,
    dots: bool = False,
) -> Iterator[str]:
    global _servers  # noqa: PLW0603
    if _servers is None:
        _servers = _start_servers(log_file, dots)
        atexit.register(_stop_servers, _servers)
    for server in _servers:
        assert_server_running(server, log_file)
    yield DJANGO_URL


if __name__ == "__main__":
    # The code below is for testing this module works
    with running_test_server(dots=True):
        print("\n\n SERVER IS UP!\n\n")
        time.sleep(10)
