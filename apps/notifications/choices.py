from django.utils.translation import gettext_lazy as _

RECIPIENT_ROLE_CHOICES = (
    (1, _("ADMIN")),
    (2, _("MEMBER")),
)

NOTIFICATION_TYPE_CHOICES = (
    (1, _("JOB_POSTED")),
    (2, _("TASK_ASSIGNED")),
    (3, _("TASK_SUBMITTED")),
    (4, _("TASK_APPROVED")),
    (5, _("TASK_REJECTED")),
)
