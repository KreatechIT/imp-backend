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
    (6, _("RENDER_READY")),
    (7, _("APPLICATION_APPROVED")),
    (8, _("APPLICATION_REJECTED")),
    (9, _("RESULT_PENDING")),
    (10, _("RESULT_COMPLETED")),
    (11, _("PAYOUT_REQUESTED")),
    (12, _("PAYOUT_APPROVED")),
    (13, _("PAYOUT_REJECTED")),
    (14, _("PAYOUT_PAID")),
    (15, _("RESULT_SUBMITTED")),
    (16, _("RESULT_APPROVED")),
    (17, _("RESULT_REJECTED")),
)
