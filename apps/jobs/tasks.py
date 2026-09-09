from celery import shared_task
from django.db.models import Count, Q

from apps.notifications import helper_functions as notifications


@shared_task
def send_pending_result_reminders():
    from apps.jobs import models

    queryset = models.MemberJob.objects.filter(archived=None).annotate(
        pending_result_count=Count(
            "tasks",
            filter=Q(
                tasks__submitted_at__isnull=False,
                tasks__metrics_submitted_at__isnull=True,
            ),
            distinct=True,
        ),
    ).filter(pending_result_count__gt=0).select_related("member__user", "job")

    for member_job in queryset:
        count = member_job.pending_result_count
        notifications.notify(
            recipient=member_job.member.user,
            role=2,
            notification_type=9,
            title="Results still needed",
            message=f"{member_job.job.title} — {count} day{'s' if count != 1 else ''} still need a result",
        )
