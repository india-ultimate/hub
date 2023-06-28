import os
from pathlib import Path

from hub.settings import *  # noqa

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)
DATABASES["default"]["NAME"] = Path("/data") / "production.db.sqlite"
