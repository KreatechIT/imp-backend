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


class DummyInfluencer(TimeStampedModel):
    full_name = models.CharField(
        verbose_name=_("Full Name"),
        max_length=150,
    )
    phone_number = models.CharField(
        verbose_name=_("Phone Number"),
        max_length=30,
        blank=True,
        default="",
    )
    deposit_amount = models.DecimalField(
        verbose_name=_("Deposit Amount"),
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    reg_count = models.PositiveIntegerField(
        verbose_name=_("Registrations"),
        default=0,
    )
    cvs_count = models.PositiveIntegerField(
        verbose_name=_("Conversions"),
        default=0,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        return self.full_name

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class InfluencerSyncRun(TimeStampedModel):
    """One attempt to pull the influencer ranking from the third party.
    Runs are never deleted: ``created`` is the sync time, and the newest
    successful run is the board that members see."""

    slot = models.IntegerField(
        verbose_name=_("Slot"),
        choices=choices.INFLUENCER_SYNC_SLOT_CHOICES,
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.INFLUENCER_SYNC_STATUS_CHOICES,
    )
    attempt = models.PositiveSmallIntegerField(
        verbose_name=_("Attempt"),
        default=1,
    )
    row_count = models.PositiveIntegerField(
        verbose_name=_("Row Count"),
        default=0,
    )
    not_found = models.JSONField(
        verbose_name=_("Not Found"),
        default=list,
        blank=True,
    )
    error = models.TextField(
        verbose_name=_("Error"),
        blank=True,
        default="",
    )

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status", "created"]),
        ]

    def __str__(self):
        stamp = f"{self.created:%Y-%m-%d %H:%M}"
        return f"{self.get_slot_display()} {self.get_status_display()} {stamp}"


class InfluencerSnapshot(models.Model):
    """One influencer's row in a sync run, kept exactly as received."""

    run = models.ForeignKey(
        InfluencerSyncRun,
        verbose_name=_("Run"),
        on_delete=models.CASCADE,
        related_name="rows",
    )
    rank = models.PositiveIntegerField(verbose_name=_("Rank"))
    member_uuid = models.CharField(
        verbose_name=_("Member Uuid"),
        max_length=36,
    )
    full_name = models.CharField(
        verbose_name=_("Full Name"),
        max_length=150,
        blank=True,
        default="",
    )
    phone_number = models.CharField(
        verbose_name=_("Phone Number"),
        max_length=30,
        blank=True,
        default="",
    )
    reg_count = models.PositiveIntegerField(default=0)
    cvs_count = models.PositiveIntegerField(default=0)
    deposit_amount = models.DecimalField(
        verbose_name=_("Deposit Amount"),
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = ["rank"]
        indexes = [
            models.Index(fields=["run", "rank"]),
            models.Index(fields=["run", "phone_number"]),
        ]


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
