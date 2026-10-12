import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from hub.settings import *  # noqa: F403

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = bool(int(os.environ.get("SECURE_SSL_REDIRECT", "1")))
SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)  # noqa: F405
EMAIL_INVITATION_BASE_URL = "https://hub.indiaultimate.org"

if os.environ.get("REDIS_HOST"):
    from redis.backoff import NoBackoff
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.retry import Retry

    from hub.redis_auth import password

    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": f"redis://:{password(SECRET_KEY)}@{os.environ['REDIS_HOST']}:6379/0",
            # Fail fast: an unreachable cache must cost a request at most 0.3 s.
            "OPTIONS": {  # type: ignore[dict-item]
                "socket_connect_timeout": 0.1,
                "socket_timeout": 0.2,
                # A pooled connection can be dead after a resume or a Redis restart:
                # reconnect once, at once. Retry's default also covers timeouts, so
                # name ConnectionError only: an unreachable Redis still costs one timeout.
                "retry": Retry(NoBackoff(), 1, supported_errors=(RedisConnectionError,)),
                "retry_on_error": [RedisConnectionError],
            },
        }
    }

if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config()  # type: ignore[assignment]  # noqa: F405
    # Reused for a minute, and checked first, rather than a new one per request.
    DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405
elif os.environ.get("FLY_APP_NAME") == "upai-hub":
    # Or it would run on a SQLite file that the next deploy throws away.
    raise ImproperlyConfigured("DATABASE_URL is not set")
# Uploaded files live on Cloudinary; the machines have no disk that lasts.
STORAGES["default"] = {"BACKEND": "server.storage.cloudinary.CloudinaryStorage"}  # noqa: F405

SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # A tenth of requests traced. Errors are sampled apart (sample_rate,
        # left at 1.0), so every one is still sent.
        traces_sample_rate=0.1,
    )
