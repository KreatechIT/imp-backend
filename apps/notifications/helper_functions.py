from django.utils import timezone

from apps.notifications import models


def notify(*, recipient, role, notification_type, title, message=None):
    if recipient is None:
        return None
    return models.Notification.objects.create(
        recipient=recipient,
        role=role,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def notify_admins(*, notification_type, title, message=None):
    from apps.crmadmin.models import Admin

    admins = Admin.objects.filter(archived=None).select_related("user")
    models.Notification.objects.bulk_create([
        models.Notification(
            recipient=admin.user,
            role=1,
            notification_type=notification_type,
            title=title,
            message=message,
        )
        for admin in admins
    ])


def notify_job_posted(job):
    from apps.members.models import Member

    message = job.title
    if job.start_date > timezone.now():
        opens_at = timezone.localtime(job.start_date)
        message = f"{job.title} - opens {opens_at:%d %b %Y}"

    members = Member.objects.filter(archived=None).select_related("user")
    models.Notification.objects.bulk_create([
        models.Notification(
            recipient=member.user,
            role=2,
            notification_type=1,
            title="New job available",
            message=message,
        )
        for member in members
    ])
