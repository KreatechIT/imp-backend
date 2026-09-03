from django.utils.translation import gettext_lazy as _

COMPANY_STATUS_CHOICES = (
    (1, _("ACTIVE")),
    (2, _("INACTIVE")),
)

JOB_STATUS_CHOICES = (
    (1, _("DRAFT")),
    (2, _("ACTIVE")),
    (3, _("PAUSED")),
    (4, _("COMPLETED")),
)

JOB_RECURRENCE_CHOICES = (
    (1, _("DAILY")),
    (2, _("WEEKLY")),
    (3, _("MONTHLY")),
)

PAYMENT_PERIOD_CHOICES = (
    (1, _("DAILY")),
    (2, _("WEEKLY")),
    (3, _("MONTHLY")),
)

PLATFORM_CHOICES = (
    (1, _("INSTAGRAM")),
    (2, _("TIKTOK")),
)

CONTENT_TYPE_CHOICES = (
    (1, _("REEL")),
    (2, _("STORY")),
    (3, _("POST")),
    (4, _("VIDEO")),
)

MEMBER_JOB_STATUS_CHOICES = (
    (1, _("APPLIED")),
    (2, _("ACTIVE")),
    (3, _("COMPLETED")),
    (4, _("REJECTED")),
)

AFFILIATE_LINK_STATUS_CHOICES = (
    (1, _("PENDING")),
    (2, _("SUBMITTED")),
    (3, _("ACTIVE")),
    (4, _("PAUSED")),
)

MEMBER_TASK_STATUS_CHOICES = (
    (1, _("PENDING")),
    (2, _("SUBMITTED")),
    (3, _("APPROVED")),
    (4, _("REJECTED")),
    (5, _("MISSED")),
)

TASK_FILE_MEDIA_TYPE_CHOICES = (
    (1, _("VIDEO")),
    (2, _("PHOTO")),
)

RENDER_STATUS_CHOICES = (
    (1, _("PROCESSING")),
    (2, _("DONE")),
    (3, _("FAILED")),
)
