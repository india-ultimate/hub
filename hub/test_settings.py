from hub.settings import *  # noqa: F403

db_name = str(BASE_DIR / "test.db.sqlite")  # noqa: F405
DATABASES["default"]["NAME"] = db_name  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": db_name}  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = str(BASE_DIR / "tmp")  # noqa: F405
