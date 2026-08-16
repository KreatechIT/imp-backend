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

# How often the work is owed. Drives the period_key used to generate tasks.
JOB_RECURRENCE_CHOICES = (
    (1, _("DAILY")),
    (2, _("WEEKLY")),
    (3, _("MONTHLY")),
)

# How the payment is quoted. Independent of recurrence.
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
