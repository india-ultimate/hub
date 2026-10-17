from typing import Any

from prometheus_client import multiprocess


def child_exit(server: Any, worker: Any) -> None:
    # Workers are recycled (max-requests): a gone one's live gauges would
    # otherwise be reported forever.
    # ponytail: its counter files stay until the next boot, so a scrape reads
    # one more set per recycle; clear the folder on a schedule if that shows.
    multiprocess.mark_process_dead(worker.pid)
