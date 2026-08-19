import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.front_view import choices
from base.models import TimeStampedModel
from core import encryption


def banner_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"banner/{uuid4().hex}{ext}"


class Banner(TimeStampedModel):
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=150,
    )
    image = ImageField(
        verbose_name=_("Banner Image"),
        blank=True,
        null=True,
        upload_to=banner_upload_to,
        validators=[encryption.validate_file_size],
    )
    link = models.URLField(
        verbose_name=_("Link"),
        max_length=500,
        blank=True,
        null=True,
    )
    location = models.IntegerField(
        verbose_name=_("Location"),
        choices=choices.BANNER_LOCATION_CHOICES,
        default=1,
    )
    active_from = models.DateTimeField(
        verbose_name=_("Active From"),
        blank=True,
        null=True,
    )
    active_until = models.DateTimeField(
        verbose_name=_("Active Until"),
        blank=True,
        null=True,
    )
    ordering = models.PositiveSmallIntegerField(
        verbose_name=_("Ordering"),
        default=0,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return self.name

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def is_live(self):
        now = timezone.now()
        if self.archived:
            return False
        if self.active_from and now < self.active_from:
            return False
        if self.active_until and now > self.active_until:
            return False
        return True


class Guide(TimeStampedModel):
    """The info card shown on one screen, filled in by an admin."""

    location = models.IntegerField(
        verbose_name=_("Location"),
        choices=choices.GUIDE_LOCATION_CHOICES,
    )
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=150,
        blank=True,
        null=True,
    )
    content = models.TextField(verbose_name=_("Content"))
    ordering = models.PositiveSmallIntegerField(
        verbose_name=_("Ordering"),
        default=0,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["location"]),
        ]

    def __str__(self):
        return f"{self.get_location_display()} - {self.title or self.uuid}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class TermsAndConditions(TimeStampedModel):
    category = models.IntegerField(
        verbose_name=_("Category"),
        choices=choices.TERMS_CATEGORY_CHOICES,
        unique=True,
    )
    content = models.TextField(verbose_name=_("Content"))

    class Meta:
        verbose_name = "Terms and Conditions"
        verbose_name_plural = "Terms and Conditions"
        indexes = [
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.get_category_display()
