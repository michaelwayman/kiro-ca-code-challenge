"""Auth service settings. All deployment-specific values come from ``config.env`` (Req 10.1)."""

from pathlib import Path

import dj_database_url

from config.env import env_bool, env_list, env_path, env_str, require_safe_secret

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core -------------------------------------------------------------------

# Defaults to False, so a missing DJANGO_DEBUG is the safe value (D-033).
DEBUG = env_bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env_str("DJANGO_SECRET_KEY")
require_safe_secret(SECRET_KEY, debug=DEBUG)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# django.contrib.auth (with the custom UUID-keyed user model, D-021) is added in spec 2,
# together with its first migration, so the user model is never swapped after migrating.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

# --- Database (D-002) -------------------------------------------------------

DATABASES = {
    "default": dj_database_url.parse(
        env_str("AUTH_DATABASE_URL"), conn_max_age=60, conn_health_checks=True
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Signing key (Req 5.2, D-031) -------------------------------------------
# The PEM file on the `auth_keys` volume. Created in DEBUG by `ensure_signing_key`;
# outside DEBUG it must already exist, or the entrypoint refuses to start.
AUTH_SIGNING_KEY_PATH = env_path("AUTH_SIGNING_KEY_PATH", default=Path("/run/keys/signing.pem"))

# --- I18N / time ------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- Static (WhiteNoise, D-033/D-034) ---------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- DRF: secure by default (design §6.1, D-034.4) --------------------------
#
# Every endpoint requires authentication unless it opts out explicitly with
# `authentication_classes = ()` and `permission_classes = (AllowAny,)`.
# The JWT authentication class from auth_common is added in spec 2.
# UNAUTHENTICATED_USER is None because django.contrib.auth isn't installed yet.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Brand Reviews Auth Service",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Logging (Req 11.3) -----------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["stdout"], "level": "INFO"},
}
