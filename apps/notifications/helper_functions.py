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

    members = Member.objects.filter(archived=None).select_related("user")
    models.Notification.objects.bulk_create([
        models.Notification(
            recipient=member.user,
            role=2,
            notification_type=1,
            title="New job available",
            message=job.title,
        )
        for member in members
    ])
