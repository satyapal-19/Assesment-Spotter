import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

# Nothing here is signed or kept in a session, so a key that changes on restart is fine when
# none is configured.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Trips are computed per request and forecasts live in the cache, so there is nothing to persist.
DATABASES = {}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        # A cached forecast is about 9 KB, so this keeps the cache near 50 MB at most.
        "OPTIONS": {"MAX_ENTRIES": 6_000},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "trips.api.errors.exception_handler",
    # Per client address. Planning a trip takes two requests: the routes, then the heatmap.
    "DEFAULT_THROTTLE_RATES": {"trips": "30/min", "places": "120/min"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"trips": {"handlers": ["console"], "level": "INFO"}},
}

USE_TZ = True
TIME_ZONE = "UTC"

TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")
TOMTOM_BASE_URL = os.environ.get("TOMTOM_BASE_URL", "https://api.tomtom.com")
