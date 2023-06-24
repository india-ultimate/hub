import os

from hub.settings import *  # noqa

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECRET_KEY = os.environ.get("SECRET_KEY", SECRET_KEY)
