import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.frames import choices
from apps.jobs.choices import TASK_FILE_MEDIA_TYPE_CHOICES
from apps.jobs.models import Job
from base.models import TimeStampedModel
from core import encryption


def frame_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"frame/{uuid4().hex}{ext}"


def rendered_content_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"content/{uuid4().hex}{ext}"


class Frame(TimeStampedModel):
    """An overlay an admin uploads for one job.

    The backend keeps the library, says which frames belong to which
    job, and composites the overlay server-side (see apps.frames.tasks).
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


class RenderedContent(TimeStampedModel):
    """One member-uploaded photo/video composited with a frame.

    Standalone: the Frame Editor is not tied to a task or a submission,
    only to a job (through its frame). The original upload is kept for
    the admin content library; the rendered file is produced by a
    background worker (FFmpeg), see apps.jobs.tasks.
    """

    frame = models.ForeignKey(
        Frame,
        verbose_name=_("Frame"),
        on_delete=models.CASCADE,
        related_name="renders",
    )
    member = models.ForeignKey(
        "members.Member",
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="rendered_content",
    )
    original_file = models.FileField(
        upload_to=rendered_content_upload_to,
        validators=[encryption.validate_content_file_size],
    )
    media_type = models.IntegerField(
        verbose_name=_("Media Type"),
        choices=TASK_FILE_MEDIA_TYPE_CHOICES,
    )
    original_name = models.CharField(
        verbose_name=_("Original Name"),
        max_length=255,
        blank=True,
        null=True,
    )
    rendered_file = models.FileField(
        upload_to=rendered_content_upload_to,
        blank=True,
        null=True,
    )
    render_status = models.IntegerField(
        verbose_name=_("Render Status"),
        choices=choices.RENDER_STATUS_CHOICES,
        default=1,
    )

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["frame"]),
            models.Index(fields=["member"]),
        ]

    def __str__(self):
        return f"{self.member} - {self.frame}"
