from .base import *  # noqa: F401,F403
from decouple import config


SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="*", cast=lambda v: [h.strip() for h in v.split(",")],
)

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 60,
    }
}

MIDDLEWARE = [
    "core.middleware.CleanHostMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = config("MEDIA_ROOT", default="/var/www/imp-media/")

STATIC_URL = config("STATIC_URL", default="/static/")
STATIC_ROOT = config("STATIC_ROOT", default="/var/www/imp-static/")

IMAGE_STRUCTURE = config("IMAGE_STRUCTURE", default="")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="",
    cast=lambda v: [o.strip() for o in v.split(",") if o.strip()],
)

ENVIRONMENT = "staging"
