from django.utils.translation import gettext_lazy as _

ASPECT_RATIO_CHOICES = (
    (1, _("9:16")),
    (2, _("1:1")),
    (3, _("4:5")),
)

# What the frame may be placed on. The editor imports either a video or a
# photo, so it only offers the frames that fit what was imported.
FRAME_MEDIA_TYPE_CHOICES = (
    (1, _("BOTH")),
    (2, _("VIDEO")),
    (3, _("PHOTO")),
)

FRAME_STATUS_CHOICES = (
    (1, _("ACTIVE")),
    (2, _("INACTIVE")),
)
