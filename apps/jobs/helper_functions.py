import calendar
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.jobs import models


def _month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def resolve_period(job, on_date=None):
    """The period covering on_date, clipped to the job's own window."""
    day = on_date or timezone.localdate()

    if job.recurrence == 1:
        period_key, start, end = day.isoformat(), day, day
    elif job.recurrence == 2:
        iso_year, iso_week, iso_weekday = day.isocalendar()
        start = day - timedelta(days=iso_weekday - 1)
        period_key, end = f"{iso_year}-W{iso_week:02d}", start + timedelta(days=6)
    else:
        start = day.replace(day=1)
        period_key, end = day.strftime("%Y-%m"), _month_end(day)

    start = max(start, timezone.localtime(job.start_date).date())
    if job.end_date:
        end = min(end, timezone.localtime(job.end_date).date())
    return period_key, start, end


def live_member_jobs(member_uuid):
    """The member's jobs that are open for work right now."""
    now = timezone.now()
    return (
        models.MemberJob.objects
        .filter(
            member__uuid=member_uuid,
            archived=None,
            status=2,
            job__archived=None,
            job__status=2,
            job__company__status=1,
            job__start_date__lte=now,
        )
        .filter(Q(job__end_date__isnull=True) | Q(job__end_date__gte=now))
        .select_related("job__company")
    )


def ensure_today_tasks(member_uuid):
    """Create this period's tasks on first read, the way missions enrol.

    Nothing is generated ahead of time, so a job that is edited, paused or
    archived simply stops producing tasks and leaves nothing stale behind.
    """
    period_keys = []
    pending = []

    for member_job in live_member_jobs(member_uuid):
        period_key, period_start, period_end = resolve_period(member_job.job)
        period_keys.append(period_key)

        for requirement in member_job.job.requirements.filter(archived=None):
            pending.append(
                models.MemberTask(
                    member_job=member_job,
                    requirement=requirement,
                    period_key=period_key,
                    period_start=period_start,
                    period_end=period_end,
                )
            )

    # the unique constraint absorbs the rows that are already there
    models.MemberTask.objects.bulk_create(pending, ignore_conflicts=True)

    today = timezone.localdate()
    return (
        models.MemberTask.objects
        .filter(
            member_job__member__uuid=member_uuid,
            member_job__archived=None,
            period_start__lte=today,
            period_end__gte=today,
            period_key__in=period_keys,
        )
        .select_related("member_job__job__company", "requirement")
        .order_by("member_job__job__company__name", "requirement__content_type")
    )
