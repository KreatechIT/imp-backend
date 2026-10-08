import os
from celery import Celery
from celery.schedules import crontab

from apps.front_view import choices as front_view_choices

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

# Crontabs are evaluated in CELERY_TIMEZONE (Asia/Kuala_Lumpur). The times
# live in front_view.choices.INFLUENCER_SYNC_SCHEDULE.
for _slot, _when in front_view_choices.INFLUENCER_SYNC_SCHEDULE.items():
    app.conf.beat_schedule[f"sync-influencer-leaderboard-{_slot}"] = {
        "task": "apps.front_view.tasks.sync_influencer_leaderboard",
        "schedule": crontab(hour=_when["hour"], minute=_when["minute"]),
        "args": (_slot,),
    }
