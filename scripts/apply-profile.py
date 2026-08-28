#!/usr/bin/env python3
"""Apply a named scaling profile from deploy/profiles.json to fly.toml.

VM size, gunicorn workers/threads and the proxy concurrency limits move together:
the limits must track workers x threads, or the proxy admits more than the app can
serve and the excess queues until it 504s. Each edit is made exactly once and read
back with tomllib, so a bad substitution fails here rather than at deploy time.

Usage: scripts/apply-profile.py <profile> [--fly-toml PATH] [--profiles PATH]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import tomllib

ROOT = Path(__file__).parent.parent
FLY_TOML = ROOT / "fly.toml"
PROFILES = ROOT / "deploy" / "profiles.json"


def _replace_once(text: str, key: str, value: str, *, quoted: bool) -> str:
    """Replace a single `key = value` assignment, insisting it appears once."""
    pattern = rf'^(?P<lead>[ \t]*{re.escape(key)}[ \t]*=[ \t]*)(?:"[^"]*"|\d+)[ \t]*$'
    replacement = f'"{value}"' if quoted else value

    def _substitute(match: re.Match[str]) -> str:
        return match.group("lead") + replacement

    new_text, count = re.subn(pattern, _substitute, text, flags=re.MULTILINE)
    if count != 1:
        sys.exit(f"error: expected exactly one '{key}' assignment in fly.toml, found {count}")
    return new_text


def _verify(path: Path, profile: dict[str, Any]) -> None:
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    vm = data["vm"][0]
    concurrency = data["services"][0]["concurrency"]
    env = data["env"]
    actual = {
        "cpu_kind": vm["cpu_kind"],
        "cpus": vm["cpus"],
        "memory": vm["memory"],
        "workers": int(env["GUNICORN_WORKERS"]),
        "threads": int(env["GUNICORN_THREADS"]),
        "soft_limit": concurrency["soft_limit"],
        "hard_limit": concurrency["hard_limit"],
    }
    for key, found in actual.items():
        expected = profile[key]
        if found != expected:
            sys.exit(f"error: {key} is {found!r} after writing, expected {expected!r}")

    slots = actual["workers"] * actual["threads"]
    if actual["soft_limit"] > slots:
        sys.exit(
            f"error: soft_limit {actual['soft_limit']} exceeds {slots} gunicorn slots "
            f"({actual['workers']} workers x {actual['threads']} threads)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="Profile name from deploy/profiles.json")
    parser.add_argument("--fly-toml", type=Path, default=FLY_TOML)
    parser.add_argument("--profiles", type=Path, default=PROFILES)
    args = parser.parse_args()

    profiles: dict[str, Any] = json.loads(args.profiles.read_text())
    if args.profile not in profiles:
        sys.exit(f"error: unknown profile {args.profile!r}; have {', '.join(sorted(profiles))}")
    profile = profiles[args.profile]

    text = args.fly_toml.read_text()
    for key, toml_key, quoted in (
        ("cpu_kind", "cpu_kind", True),
        ("cpus", "cpus", False),
        ("memory", "memory", True),
        ("workers", "GUNICORN_WORKERS", True),
        ("threads", "GUNICORN_THREADS", True),
        ("soft_limit", "soft_limit", False),
        ("hard_limit", "hard_limit", False),
    ):
        text = _replace_once(text, toml_key, str(profile[key]), quoted=quoted)

    args.fly_toml.write_text(text)
    _verify(args.fly_toml, profile)

    slots = profile["workers"] * profile["threads"]
    kind = profile["cpu_kind"]
    size = (
        f"shared-cpu-{profile['cpus']}x" if kind == "shared" else f"performance-{profile['cpus']}x"
    )
    print(
        f"Applied '{args.profile}': {size}, {profile['memory']}, "
        f"{profile['workers']}w x {profile['threads']}t = {slots} slots, "
        f"limits {profile['soft_limit']}/{profile['hard_limit']}"
    )


if __name__ == "__main__":
    main()
