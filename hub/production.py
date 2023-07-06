import os
from pathlib import Path

from hub.settings import *  # noqa

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = bool(int(os.environ.get("SECURE_SSL_REDIRECT", "1")))
SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)

DATA_DIR = Path("/data")
DATABASES["default"]["NAME"] = DATA_DIR / "production.db.sqlite"
MEDIA_ROOT = DATA_DIR / "media"
STATIC_ROOT = "/tmp/static/"
