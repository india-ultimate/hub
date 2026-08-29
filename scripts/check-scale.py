#!/usr/bin/env python3
"""Warn when the shared-CPU burst balance is draining for real.

Depth alone cannot tell a drain from a deploy -- over the 15 days to 2026-08-28 the
deploy dips bottomed lower (9,983 and 15,332) than the level the real incident sat
at for six hours. Duration can: deploys recovered within 90 minutes, the incident
never did. Hence the sustained-window test rather than a threshold.

Writes `escalate=true|false` to $GITHUB_OUTPUT. Needs FLY_METRICS_TOKEN, which
must be org-scoped; the app-scoped FLY_API_TOKEN is accepted but gets a 403.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HTTP_FORBIDDEN = 403
MAX_ERROR_BODY = 2048

ROOT = Path(__file__).parent.parent
ORG = os.environ.get("FLY_ORG", "upai")
APP = os.environ.get("FLY_APP", "upai-hub")

SUSTAINED_CEILING = int(os.environ.get("SUSTAINED_CEILING", "60000"))
SUSTAINED_WINDOW = os.environ.get("SUSTAINED_WINDOW", "2h")

# Backstop, set below the deepest deploy dip on record (9,983).
FLOOR = int(os.environ.get("BALANCE_FLOOR", "5000"))
FLOOR_WINDOW = os.environ.get("FLOOR_WINDOW", "15m")


def http_error_message(code: int, body: bytes) -> str:
    """A deploy token authenticates but is app-scoped, so org metrics give 403.
    A bad token gives 401."""
    hint = ""
    if code == HTTP_FORBIDDEN:
        hint = (
            f" A deploy token cannot read org metrics -- set FLY_METRICS_TOKEN to"
            f" a read-only org token (fly tokens create readonly -o {ORG})."
        )
    message = f"error: metrics API returned {code}.{hint}"
    detail = body.decode(errors="replace").strip()
    return f"{message} {detail}" if detail else message


def decide(kind: str, peak: float | None, trough: float | None) -> tuple[bool, str]:
    """Escalate only on a drain that has not recovered for the whole window; a
    deploy dip always does."""
    if kind != "shared":
        return False, f"already on a {kind} profile, nothing to escalate to"
    if peak is None or trough is None:
        # Usually a stopped or just-replaced Machine.
        return False, "no cpu_balance samples returned"
    if peak < SUSTAINED_CEILING:
        return True, (
            f"balance has not recovered above {SUSTAINED_CEILING} in "
            f"{SUSTAINED_WINDOW} (peak {peak:.0f})"
        )
    if trough < FLOOR:
        return True, f"balance fell below the {FLOOR} floor (min {trough:.0f})"
    return False, f"healthy: {SUSTAINED_WINDOW} peak {peak:.0f}, {FLOOR_WINDOW} min {trough:.0f}"


def _query(promql: str, token: str) -> float | None:
    url = f"https://api.fly.io/prometheus/{ORG}/api/v1/query"
    body = urllib.parse.urlencode({"query": promql}).encode()
    # Macaroon tokens are rejected under the Bearer scheme.
    request = urllib.request.Request(url, data=body, headers={"Authorization": f"FlyV1 {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload: dict[str, Any] = json.load(response)
    except urllib.error.HTTPError as exc:
        sys.exit(http_error_message(exc.code, exc.read(MAX_ERROR_BODY)))
    if payload.get("status") != "success":
        sys.exit(f"error: Prometheus query failed: {json.dumps(payload)[:300]}")
    results: list[dict[str, Any]] = payload["data"]["result"]
    if not results:
        return None
    return float(results[0]["value"][1])


def _current_cpu_kind() -> str:
    # Not tomllib: this runs on a bare runner with no install, and the repo
    # supports Python 3.10, where tomllib does not exist.
    match = re.search(r'^\s*cpu_kind\s*=\s*"([^"]+)"', (ROOT / "fly.toml").read_text(), re.M)
    if match is None:
        sys.exit("error: no cpu_kind found in fly.toml")
    return match.group(1)


def _emit(escalate: bool, reason: str) -> None:
    print(f"escalate={escalate}: {reason}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"escalate={'true' if escalate else 'false'}\n")
            handle.write(f"reason={reason}\n")


def main() -> None:
    # Prefer a metrics-scoped token; FLY_API_TOKEN is the app-scoped deploy token.
    token = os.environ.get("FLY_METRICS_TOKEN") or os.environ.get("FLY_API_TOKEN")
    if not token:
        sys.exit("error: neither FLY_METRICS_TOKEN nor FLY_API_TOKEN is set")

    kind = _current_cpu_kind()
    if kind != "shared":
        _emit(*decide(kind, None, None))
        return

    metric = f'fly_instance_cpu_balance{{app="{APP}"}}'
    peak = _query(f"max_over_time({metric}[{SUSTAINED_WINDOW}])", token)
    trough = _query(f"min_over_time({metric}[{FLOOR_WINDOW}])", token)

    _emit(*decide(kind, peak, trough))


if __name__ == "__main__":
    main()
