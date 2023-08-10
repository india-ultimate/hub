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
MAX_SERVER_WAIT = 30
PORT = 9981
WEBPACK_SERVER_PORT = 9982
HTTP_SUCCESS = 200


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


@contextmanager
def running_test_server(
    log_file: str | None = None,
    dots: bool = False,
) -> Iterator[str]:
    log = sys.stdout
    set_up_django()
    # subprocess.run(["./manage.py", "migrate", "--no-input"])

    # Start Django server
    dev_server_command = ["./manage.py", "runserver", str(PORT)]
    django_server = subprocess.Popen(
        dev_server_command, stdout=log, stderr=log, cwd=ROOT  # noqa: S603
    )
    django_base_url = f"http://localhost:{PORT}"

    dev_server_command = [
        str(FRONTEND_DIR / "node_modules/.bin/webpack-dev-server"),
        "--config",
        str(HERE / "tests.webpack.config.js"),
        "--mode",
        "development",
    ]
    webpack_server = subprocess.Popen(
        dev_server_command, stdout=log, stderr=log, cwd=FRONTEND_DIR  # noqa: S603
    )
    webpack_base_url = f"http://localhost:{WEBPACK_SERVER_PORT}"

    try:
        wait_server_start(django_server, f"{django_base_url}/api/docs", log_file, dots)
        wait_server_start(webpack_server, webpack_base_url, log_file, dots)

        # DO OUR ACTUAL TESTING HERE!!!
        yield django_base_url

    finally:
        assert_server_running(webpack_server, log_file)
        webpack_server.terminate()

        assert_server_running(django_server, log_file)
        django_server.terminate()

        webpack_server.wait()
        django_server.wait()


if __name__ == "__main__":
    # The code below is for testing this module works
    with running_test_server(dots=True):
        print("\n\n SERVER IS UP!\n\n")
        time.sleep(10)
