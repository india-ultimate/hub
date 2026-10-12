"""Redis access for the page cache: versions, pages and lookups.

Knows nothing about URLs, views or models. Every call fails open.
"""

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from django.core.cache import cache, caches
from django.core.cache.backends.dummy import DummyCache
from django.db import transaction

log = logging.getLogger("server.cache")
T = TypeVar("T")

TTL = 30
# A match never changes tournament, so its lookup can last. A slug can be
# recreated under a new id, so its lookup lasts no longer than a page.
MATCH_LOOKUP_TTL = 24 * 60 * 60
PAUSE = 5
# The scope of the tournament lists, versioned like a tournament.
ALL = "all"

_state = {"down_until": 0.0}


def reset() -> None:
    _state["down_until"] = 0.0


def enabled() -> bool:
    # `cache` is a proxy that isinstance() can't see through.
    return time.monotonic() >= _state["down_until"] and not isinstance(
        caches["default"], DummyCache
    )


def safe(call: Callable[[], T], default: T) -> T:
    if time.monotonic() < _state["down_until"]:
        return default
    try:
        return call()
    except Exception:
        # One slow or dead cache costs one timeout per process per PAUSE, not one per call.
        _state["down_until"] = time.monotonic() + PAUSE
        log.warning("Public page cache unavailable", exc_info=True)
        return default


def _version_key(tid: str) -> str:
    return f"tver:{tid}"


def version(tid: str) -> Any:
    """The tournament's version, 0 if never bumped, or None if the cache is down."""
    return safe(lambda: cache.get(_version_key(tid), 0), None)


def bump(tid: str) -> None:
    """Make every cached page of the tournament stale, once committed."""
    if not enabled():
        return

    def go() -> None:
        # A version only has to change, so one set does it.
        safe(lambda: cache.set(_version_key(tid), time.time_ns(), None), None)

    transaction.on_commit(go)


def _page_key(tid: str, version: Any, path: str) -> str:
    return f"page:{tid}:{version}:{path}"


def get_page(tid: str, version: Any, path: str) -> tuple[bytes, str] | None:
    """The stored body and content type, or None."""
    key = _page_key(tid, version, path)
    return safe(lambda: cache.get(key), None)


def set_page(tid: str, version: Any, path: str, body: bytes, content_type: str) -> None:
    key = _page_key(tid, version, path)
    entry = (body, content_type)
    safe(lambda: cache.set(key, entry, TTL), None)


def _looked_up(key: str, ttl: int, find: Callable[[], int | None]) -> str | None:
    found = safe(lambda: cache.get(key), None)
    if found is None:
        tid = find()  # The database's errors are the view's to report, not a cache outage.
        if tid is None:
            return None
        found = str(tid)
        safe(lambda: cache.set(key, found, ttl), None)
    return str(found)


def match_tournament(match_id: str, find: Callable[[], int | None]) -> str | None:
    """The match's tournament id, from the cache or else `find`. Only `find` can raise."""
    return _looked_up(f"tmatch:{match_id}", MATCH_LOOKUP_TTL, find)


def slug_tournament(slug: str, find: Callable[[], int | None]) -> str | None:
    """The slug's tournament id, from the cache or else `find`. Only `find` can raise."""
    return _looked_up(f"tslug:{slug}", TTL, find)
