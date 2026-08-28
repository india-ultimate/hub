#!/usr/bin/env python3
"""Warn when the shared-CPU burst balance is draining for real.

Depth alone cannot tell a drain from a deploy -- over the 15 days to 2026-08-28 the
deploy dips bottomed lower (9,983 and 15,332) than the level the real incident sat
at for six hours. Duration can: deploys recovered within 90 minutes, the incident
never did. Hence the sustained-window test rather than a threshold.

Writes `escalate=true|false` to $GITHUB_OUTPUT. Needs FLY_API_TOKEN.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import tomllib

ROOT = Path(__file__).parent.parent
ORG = os.environ.get("FLY_ORG", "upai")
APP = os.environ.get("FLY_APP", "upai-hub")

SUSTAINED_CEILING = int(os.environ.get("SUSTAINED_CEILING", "60000"))
SUSTAINED_WINDOW = os.environ.get("SUSTAINED_WINDOW", "2h")

# Backstop, set below the deepest deploy dip on record (9,983).
FLOOR = int(os.environ.get("BALANCE_FLOOR", "5000"))
FLOOR_WINDOW = os.environ.get("FLOOR_WINDOW", "15m")


def _query(promql: str, token: str) -> float | None:
    url = f"https://api.fly.io/prometheus/{ORG}/api/v1/query"
    body = urllib.parse.urlencode({"query": promql}).encode()
    # Macaroon tokens are rejected under the Bearer scheme.
    request = urllib.request.Request(url, data=body, headers={"Authorization": f"FlyV1 {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload: dict[str, Any] = json.load(response)
    if payload.get("status") != "success":
        sys.exit(f"error: Prometheus query failed: {json.dumps(payload)[:300]}")
    results: list[dict[str, Any]] = payload["data"]["result"]
    if not results:
        return None
    return float(results[0]["value"][1])


def _current_cpu_kind() -> str:
    with (ROOT / "fly.toml").open("rb") as handle:
        data = tomllib.load(handle)
    kind: str = data["vm"][0]["cpu_kind"]
    return kind


def _emit(escalate: bool, reason: str) -> None:
    print(f"escalate={escalate}: {reason}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"escalate={'true' if escalate else 'false'}\n")
            handle.write(f"reason={reason}\n")


def main() -> None:
    token = os.environ.get("FLY_API_TOKEN")
    if not token:
        sys.exit("error: FLY_API_TOKEN is not set")

    kind = _current_cpu_kind()
    if kind != "shared":
        _emit(False, f"already on a {kind} profile, nothing to escalate to")
        return

    metric = f'fly_instance_cpu_balance{{app="{APP}"}}'
    peak = _query(f"max_over_time({metric}[{SUSTAINED_WINDOW}])", token)
    trough = _query(f"min_over_time({metric}[{FLOOR_WINDOW}])", token)

    if peak is None or trough is None:
        # Usually a stopped or just-replaced Machine. A real drain will still be
        # there in 30 min.
        _emit(False, "no cpu_balance samples returned")
        return

    if peak < SUSTAINED_CEILING:
        _emit(
            True,
            f"balance has not recovered above {SUSTAINED_CEILING} in "
            f"{SUSTAINED_WINDOW} (peak {peak:.0f})",
        )
    elif trough < FLOOR:
        _emit(True, f"balance fell below the {FLOOR} floor (min {trough:.0f})")
    else:
        _emit(
            False,
            f"healthy: {SUSTAINED_WINDOW} peak {peak:.0f}, {FLOOR_WINDOW} min {trough:.0f}",
        )


if __name__ == "__main__":
    main()
