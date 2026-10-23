import calendar
import os
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.jobs import models
from apps.notifications import helper_functions as notifications


def _month_end(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def member_start_date(member_job):
    if member_job.joined:
        return member_job.joined
    return timezone.localtime(member_job.created).date()


def resolve_period(job, on_date=None, joined=None):
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
    if joined:
        start = max(start, joined)
    if job.end_date:
        end = min(end, timezone.localtime(job.end_date).date())
    return period_key, start, end


def live_member_jobs(member_uuid):
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
    period_keys = []
    pending = []

    for member_job in live_member_jobs(member_uuid):
        period_key, period_start, period_end = resolve_period(
            member_job.job, joined=member_start_date(member_job),
        )
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

    existing_keys = set(
        models.MemberTask.objects
        .filter(member_job__member__uuid=member_uuid, period_key__in=period_keys)
        .values_list("member_job_id", "requirement_id", "period_key")
    )
    new_tasks = [
        task for task in pending
        if (task.member_job_id, task.requirement_id, task.period_key) not in existing_keys
    ]

    models.MemberTask.objects.bulk_create(pending, ignore_conflicts=True)

    if new_tasks:
        from apps.members.models import Member
        member_user = Member.objects.select_related("user").get(uuid=member_uuid).user
        for task in new_tasks:
            notifications.notify(
                recipient=member_user,
                role=2,
                notification_type=2,
                title="New task assigned",
                message=str(task.requirement),
            )

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


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".m4v", ".webm"}


def media_type_for(filename):
    ext = os.path.splitext(filename or "")[1].lower()
    return 1 if ext in VIDEO_EXTENSIONS else 2


def _job_periods(job, last_day):
    """Every period of the job from its start up to last_day, numbered from 1."""
    day = timezone.localtime(job.start_date).date()
    periods = []
    while day <= last_day:
        period_key, start, end = resolve_period(job, day)
        periods.append((len(periods) + 1, period_key, start, end))
        day = end + timedelta(days=1)
    return periods


def member_job_days(member_job, request):
    """A member's job laid out period by period: each period's tasks and, next
    to them, the result of its story (the only content type that reports one).
    Used by the member's results page and the admin review popup."""
    job = member_job.job
    today = timezone.localdate()
    last_day = today
    if job.end_date:
        last_day = min(last_day, timezone.localtime(job.end_date).date())
    joined = member_start_date(member_job)

    requirements = list(
        job.requirements.filter(archived=None).order_by("content_type", "platform")
    )
    tasks_by_period = {}
    for task in member_job.tasks.select_related("requirement"):
        tasks_by_period.setdefault(task.period_key, {})[task.requirement_id] = task

    def file_url(field):
        return request.build_absolute_uri(field.url) if field else None

    days = []
    for number, period_key, start, end in _job_periods(job, last_day):
        if end < joined:
            continue
        existing = tasks_by_period.get(period_key, {})
        is_over = end < today

        rows = []
        story_task = None
        for requirement in requirements:
            task = existing.get(requirement.id)
            if requirement.content_type == 2:
                story_task = task
            rows.append({
                "uuid": task.uuid if task else None,
                "platform": requirement.platform,
                "content_type": requirement.content_type,
                "quantity": requirement.quantity,
                "status": task.status if task else (5 if is_over else 1),
                "submitted_at": task.submitted_at if task else None,
                "proof_link": task.proof_link if task else None,
                "proof_file": file_url(task.proof_file) if task else None,
                "reject_reason": task.reject_reason if task else None,
            })

        has_story = any(requirement.content_type == 2 for requirement in requirements)
        result = None
        if has_story:
            result = {
                "task_uuid": story_task.uuid if story_task else None,
                "can_submit": bool(
                    story_task and story_task.is_submitted and not story_task.result_locked
                ),
                "has_result": bool(story_task and story_task.has_result),
                "metrics_views": story_task.metrics_views if story_task else None,
                "metrics_screenshot": file_url(story_task.metrics_screenshot) if story_task else None,
                "metrics_submitted_at": story_task.metrics_submitted_at if story_task else None,
                "result_status": story_task.result_status if story_task else None,
                "result_reject_reason": story_task.result_reject_reason if story_task else None,
                "result_auto_approved": bool(story_task and story_task.is_result_auto_approved),
            }

        days.append({
            "number": number,
            "period_key": period_key,
            "period_start": start,
            "period_end": end,
            "is_today": start <= today <= end,
            "tasks": rows,
            "result": result,
        })
    return days
