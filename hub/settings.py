"""
Django settings for hub project.

Generated by 'django-admin startproject' using Django 4.2.1.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""
import os
from pathlib import Path
from socket import gethostname, gethostbyname 

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-22ea##0-ih5e#&6q*5c@l@(bd_@fg^5l6796l!p17@9-nu5!@9"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    "hub.indiaultimate.org",
    "upai-hub.fly.dev",
    "upai-hub-staging.fly.dev",
    "127.0.0.1",
    "localhost",
    gethostname(), 
    gethostbyname(gethostname()),
]

# Application definition

AUTH_USER_MODEL = "server.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_prometheus",
    "server",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "hub.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hub.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles/"
STATICFILES_DIRS = [BASE_DIR / "frontend" / "dist"]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}


# File upload settings
MEDIA_ROOT = BASE_DIR / "uploads"
MEDIA_URL = "/uploads/"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}

# App settings
APP_NAME = "India Ultimate Hub"
LOGO_URL = "https://hub.indiaultimate.org/static/assets/favico.png"

# Razorpay settings
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# Phonepe settings
PHONEPE_MERCHANT_ID = os.environ.get("PHONEPE_MERCHANT_ID", "")
PHONEPE_SALT_KEY = os.environ.get("PHONEPE_SALT_KEY", "")
PHONEPE_SALT_INDEX = int(os.environ.get("PHONEPE_SALT_INDEX", "1"))
PHONEPE_PRODUCTION = bool(os.environ.get("PHONEPE_PRODUCTION"))

# Webpack dev server
WEBPACK_SERVER_PORT = os.environ.get("WEBPACK_SERVER_PORT", 3000)

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "admin@indiaultimate.org")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# OTP settings
OTP_EMAIL_HASH_KEY = os.environ.get("OTP_EMAIL_HASH_KEY", "")

# Support email
EMAIL_SUPPORT = os.environ.get("EMAIL_SUPPORT", EMAIL_HOST_USER)

# Hanko Settings
PASSKEY_TENANT_ID = os.environ.get("PASSKEY_TENANT_ID", "")
PASSKEY_SECRET_API_KEY = os.environ.get("PASSKEY_SECRET_API_KEY", "")

# Prometheus Settings
PROMETHEUS_METRIC_NAMESPACE = "hub"

# OCR API Keys
OCR_API_KEY = os.environ.get("OCR_API_KEY", "")


########################################################################
import django_stubs_ext

# Monkey-patch certain types that are declared as generic types generic in
# django-stubs, but not (yet) as generic types in Django itself.
django_stubs_ext.monkeypatch()
