import copy
import importlib
import os
import sys
from typing import Any
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from server.cache import store

CONN = "redis.connection.Connection"


def production_caches(**extra_env: str) -> dict[str, Any]:
    """The CACHES that production.py builds when it has a Redis.

    production.py star-imports hub.settings and edits its dicts in place (STORAGES,
    DATABASES), the very ones the running settings share: put them back afterwards.
    CACHES is rebound, not edited, so the original is untouched.
    """
    from hub import settings as base

    shared: list[dict[str, Any]] = [base.STORAGES, base.DATABASES]
    backup = [copy.deepcopy(d) for d in shared]
    saved = sys.modules.pop("hub.production", None)
    env = {"DATABASE_URL": "", "FLY_APP_NAME": "", "SENTRY_DSN": ""}
    env |= {"REDIS_HOST": "localhost", "SECRET_KEY": "s"} | extra_env
    try:
        with mock.patch.dict(os.environ, env):
            return importlib.import_module("hub.production").CACHES
    finally:
        sys.modules.pop("hub.production", None)
        if saved:
            sys.modules["hub.production"] = saved
        for original, copied in zip(shared, backup, strict=True):
            original.clear()
            original.update(copied)


class TestProductionCachesLeaveSettingsAlone(SimpleTestCase):
    def test_loading_production_settings_changes_nothing_else(self) -> None:
        storages, databases = copy.deepcopy(settings.STORAGES), copy.deepcopy(settings.DATABASES)
        production_caches(DATABASE_URL="postgres://u:p@h/d")
        self.assertEqual(storages, settings.STORAGES)
        self.assertEqual(databases, settings.DATABASES)


class TestPooledConnectionReconnect(SimpleTestCase):
    """A pooled connection can be dead after a resume or a Redis restart."""

    def setUp(self) -> None:
        store.reset()
        self.addCleanup(store.reset)

    def first_command_fails(self, error: Exception) -> tuple[object, mock.Mock, bool]:
        send = mock.Mock(side_effect=[error, None, None, None])
        with (
            override_settings(CACHES=production_caches()),
            mock.patch(f"{CONN}.connect"),
            mock.patch(f"{CONN}.send_command", send),
            mock.patch(f"{CONN}.read_response", return_value=None),
            mock.patch(f"{CONN}.disconnect"),
        ):
            return store.version("t"), send, store.enabled()

    def test_a_dead_connection_is_retried_once(self) -> None:
        value, send, enabled = self.first_command_fails(RedisConnectionError("reset"))
        self.assertEqual(0, value)
        self.assertEqual(2, send.call_count)
        self.assertTrue(enabled)

    def test_a_timeout_is_not_retried(self) -> None:
        value, send, enabled = self.first_command_fails(RedisTimeoutError("slow"))
        self.assertIsNone(value)
        self.assertEqual(1, send.call_count)
        self.assertFalse(enabled)
