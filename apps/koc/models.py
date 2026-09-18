import os
from uuid import uuid4

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.jobs.choices import TASK_FILE_MEDIA_TYPE_CHOICES
from base.models import TimeStampedModel
from core import encryption


def submission_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"submission/{uuid4().hex}{ext}"


class Submission(TimeStampedModel):
    member = models.ForeignKey(
        "members.Member",
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="koc_submissions",
    )
    content_file = models.FileField(
        verbose_name=_("Content File"),
        upload_to=submission_upload_to,
        validators=[encryption.validate_content_file_size],
    )
    media_type = models.IntegerField(
        verbose_name=_("Media Type"),
        choices=TASK_FILE_MEDIA_TYPE_CHOICES,
    )
    published_url = models.URLField(
        verbose_name=_("Published Reel Link"),
        max_length=500,
    )

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["member"]),
        ]

    def __str__(self):
        return f"{self.member} - {self.published_url}"
