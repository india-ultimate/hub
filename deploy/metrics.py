"""Serves an app machine's Prometheus metrics to Fly's scraper (fly.toml [metrics]).

Each gunicorn worker counts on its own, so prometheus_client's multiprocess
mode has every worker write to PROMETHEUS_MULTIPROC_DIR, and this adds them
up. Kept apart from Django, a scrape needs no Host header or HTTPS and takes
no gunicorn thread.
"""

import os

from prometheus_client import CollectorRegistry, start_http_server
from prometheus_client.multiprocess import MultiProcessCollector

registry = CollectorRegistry()
MultiProcessCollector(registry)
# "::" for Fly's private network, which is IPv6.
_, thread = start_http_server(int(os.environ.get("METRICS_PORT", "9091")), "::", registry)
thread.join()
