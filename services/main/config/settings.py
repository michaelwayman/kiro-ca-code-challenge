"""Main app settings. All deployment-specific values come from ``config.env`` (Req 10.1)."""

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

# The main app owns no users, passwords or roles (Req 1.3, D-005). django.contrib.auth is
# deliberately NOT installed, and never will be. Identity arrives only as verified token
# claims (auth_common's TokenUser, spec 2).
INSTALLED_APPS = [
    # Before staticfiles, so runserver serves static through WhiteNoise as in prod (D-033).
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "catalog",
    "wp_import",
    "api",
    "pages",
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
        env_str("MAIN_DATABASE_URL"), conn_max_age=60, conn_health_checks=True
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- I18N / time ------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

# --- Static and frontend build (design §7, D-033) ---------------------------
#
# The image's Node stage writes the frontend build OUTSIDE /app, so the dev bind mount of
# the service source can't hide it:
#   <FRONTEND_DIST_DIR>/css/theme.css                  compiled SCSS (spec 4)
#   <FRONTEND_DIST_DIR>/brandlist/assets/*             Vite bundle (spec 5)
#   <FRONTEND_DIST_DIR>/brandlist/.vite/manifest.json  read from disk by pages.vite
#                                                      (collectstatic skips dot-dirs)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
FRONTEND_DIST_DIR = env_path("FRONTEND_DIST_DIR", default=Path("/opt/frontend-dist"))
# Only added when present, so local test and dev runs without a frontend build don't warn.
# A missing build still fails loudly in DEBUG through the vite_asset tag.
STATICFILES_DIRS = [FRONTEND_DIST_DIR] if FRONTEND_DIST_DIR.is_dir() else []
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Dev only: when set, templates load the bundle from the Vite dev server (design §7).
VITE_DEV_SERVER = env_str("VITE_DEV_SERVER", default="")

# --- DRF: secure by default (design §6.1, D-034.4) --------------------------
#
# Every endpoint requires authentication unless it opts out explicitly with
# `authentication_classes = ()` and `permission_classes = (AllowAny,)`, and is listed
# in tests/test_url_protection.py. The JWT authentication class from auth_common is
# added in spec 2. UNAUTHENTICATED_USER is None because there is no contrib.auth.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Brand Reviews API",
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
