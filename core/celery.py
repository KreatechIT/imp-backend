import os
from celery import Celery

django_environment = os.environ.get("DJANGO_ENV", None)

if django_environment == "production":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
elif django_environment == "staging":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.staging")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.base")


app = Celery("core")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
