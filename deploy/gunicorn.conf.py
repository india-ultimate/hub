from typing import Any

from prometheus_client import multiprocess


def child_exit(server: Any, worker: Any) -> None:
    # Workers are recycled (max-requests): a gone one's live gauges would
    # otherwise be reported forever.
    multiprocess.mark_process_dead(worker.pid)
