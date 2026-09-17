from django.utils.translation import gettext_lazy as _

PROVIDER_CHOICES = (
    (1, _("INSTAGRAM")),
    (2, _("FACEBOOK")),
)

PULL_STATUS_CHOICES = (
    (1, _("PROCESSING")),
    (2, _("DONE")),
    (3, _("FAILED")),
    (4, _("EXPIRED")),
)
