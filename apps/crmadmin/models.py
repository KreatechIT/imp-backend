import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.crmadmin import choices
from base.models import TimeStampedModel, UserModel
from core import encryption


def admin_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"admin/{uuid4().hex}{ext}"


class Admin(TimeStampedModel):
    user = models.OneToOneField(
        UserModel,
        verbose_name=_("User"),
        on_delete=models.CASCADE,
        related_name="admin",
    )
    full_name = models.CharField(
        verbose_name=_("Full Name"),
        max_length=150,
        blank=True,
        null=True,
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.ADMIN_STATUS_CHOICES,
        default=1,
    )
    profile_picture = ImageField(
        verbose_name=_("Profile Picture"),
        blank=True,
        null=True,
        upload_to=admin_upload_to,
        validators=[encryption.validate_file_size],
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.full_name or self.user.username

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class ActivityLog(TimeStampedModel):
    admin = models.ForeignKey(
        Admin,
        verbose_name=_("Admin"),
        on_delete=models.CASCADE,
        related_name="activity_log",
    )
    activity = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
        ]
