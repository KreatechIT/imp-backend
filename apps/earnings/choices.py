from django.utils.translation import gettext_lazy as _

PAYOUT_STATUS_CHOICES = (
    (1, _("PENDING")),
    (2, _("PAID")),
)

JOB_PAYOUT_STATUS_CHOICES = (
    (1, _("PENDING")),
    (2, _("APPROVED")),
    (3, _("REJECTED")),
    (4, _("PAID")),
)
