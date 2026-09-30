import os

from hub.settings import *  # noqa: F403

db_name = str(BASE_DIR / "test.db.sqlite")  # noqa: F405
DATABASES["default"]["NAME"] = db_name  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": db_name}  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = str(BASE_DIR / "tmp")  # noqa: F405

# Fixed, so the tests and the server the browser tests start read each
# other's rows. Only ever encrypts test keys.
PAYMENT_ACCOUNT_ENCRYPTION_KEY = (
    os.environ.get("PAYMENT_ACCOUNT_ENCRYPTION_KEY")
    or "i7aXtOZ487xBNFK80Hfy8VNPki_5uB72Vrn_CHIeo_A="
)
