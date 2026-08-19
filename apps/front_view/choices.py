from django.utils.translation import gettext_lazy as _

BANNER_LOCATION_CHOICES = (
    (1, _("HOME BANNER")),
    (2, _("EVENT BANNER")),
    (3, _("POST OF THE DAY")),
)

GUIDE_LOCATION_CHOICES = (
    (1, _("HOME")),
    (2, _("MISSION TODAY")),
    (3, _("EARNING")),
    (4, _("MISSED")),
    (5, _("RULES")),
    (6, _("LEADERBOARD")),
    (7, _("JOB BOARD")),
    (8, _("AFFILIATE LINKS")),
    (9, _("PROFILE")),
    (10, _("BANK DETAILS")),
)

TERMS_CATEGORY_CHOICES = (
    (1, _("EARNINGS")),
    (2, _("LEADERBOARD")),
    (3, _("JOB")),
)
