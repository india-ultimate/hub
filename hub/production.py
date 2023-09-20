import os
from pathlib import Path

import dj_database_url

from hub.settings import *  # noqa: F403

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = bool(int(os.environ.get("SECURE_SSL_REDIRECT", "1")))
SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)  # noqa: F405

DATA_DIR = Path("/data")
if os.environ.get("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.config()  # type: ignore[assignment]  # noqa: F405
else:
    DATABASES["default"]["NAME"] = DATA_DIR / "production.db.sqlite"  # noqa: F405
MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "/media/"
