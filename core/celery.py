import os
from celery import Celery
from celery.schedules import crontab

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

app.conf.beat_schedule = {
    "send-pending-result-reminders": {
        "task": "apps.jobs.tasks.send_pending_result_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
}
