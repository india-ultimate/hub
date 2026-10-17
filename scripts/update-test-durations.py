#!/usr/bin/env python
"""Refresh .test_durations from a CI run's browser-test timings.

pytest-split balances the integration groups by that file, and gives a test it
doesn't know the average. Run this when the groups drift apart:

    scripts/update-test-durations.py [RUN_ID]    # default: the latest run on main
"""

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parents[1]


def node_id(case: ET.Element) -> str:
    """server.tests.test_ui.TestIntegration + test_x -> server/tests/test_ui.py::TestIntegration::test_x"""
    *module, cls = case.attrib["classname"].split(".")
    return f"{'/'.join(module)}.py::{cls}::{case.attrib['name']}"


def durations(folder: Path) -> dict[str, float]:
    return {
        node_id(case): round(float(case.attrib["time"]), 3)
        for report in folder.rglob("*.xml")
        for case in ET.parse(report).iter("testcase")  # noqa: S314 - our own CI's output
        if case.find("skipped") is None
    }


def main() -> None:
    run = sys.argv[1] if len(sys.argv) > 1 else None
    if run is None:
        run = subprocess.check_output(
            ["gh", "run", "list", "--branch", "main", "--workflow", "CI Tests", "--limit", "1",
             "--json", "databaseId", "-q", ".[0].databaseId"],
            text=True,
        ).strip()
    with tempfile.TemporaryDirectory() as folder:
        subprocess.run(  # noqa: S603
            ["gh", "run", "download", run, "-p", "durations-*", "-D", folder],  # noqa: S607
            check=True,
        )
        found = durations(Path(folder))
    if not found:
        sys.exit(f"run {run} has no test durations")
    path = ROOT / ".test_durations"
    path.write_text(json.dumps(dict(sorted(found.items())), indent=2) + "\n")
    print(f"{len(found)} tests from run {run}")


if __name__ == "__main__":
    main()
