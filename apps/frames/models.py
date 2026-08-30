import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.frames import choices
from apps.jobs.models import Job
from base.models import TimeStampedModel
from core import encryption


def frame_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"frame/{uuid4().hex}{ext}"


class Frame(TimeStampedModel):
    """An overlay an admin uploads for one job.

    The compositing happens in the client; the backend only keeps the
    library and says which frames belong to which job.
    """

    job = models.ForeignKey(
        Job,
        verbose_name=_("Job"),
        on_delete=models.CASCADE,
        related_name="frames",
    )
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=150,
    )
    image = ImageField(
        verbose_name=_("Frame Image"),
        upload_to=frame_upload_to,
        validators=[
            encryption.validate_file_size,
            encryption.validate_transparent_image,
        ],
    )
    aspect_ratio = models.IntegerField(
        verbose_name=_("Aspect Ratio"),
        choices=choices.ASPECT_RATIO_CHOICES,
        default=1,
    )
    media_type = models.IntegerField(
        verbose_name=_("Media Type"),
        choices=choices.FRAME_MEDIA_TYPE_CHOICES,
        default=1,
    )
    ordering = models.PositiveSmallIntegerField(
        verbose_name=_("Ordering"),
        default=0,
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.FRAME_STATUS_CHOICES,
        default=1,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
            models.Index(fields=["media_type"]),
        ]

    def __str__(self):
        return f"{self.job} - {self.name}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def is_live(self):
        return self.status == 1 and self.archived is None

    def accepts(self, media_type):
        """BOTH frames fit either import; the rest must match exactly."""
        return self.media_type == 1 or self.media_type == media_type
