import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.jobs import choices
from base.models import TimeStampedModel
from core import encryption


def company_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"company/{uuid4().hex}{ext}"


class JobSettings(TimeStampedModel):
    singleton_enforcer = models.BooleanField(default=True, unique=True)
    default_deduction_per_miss = models.DecimalField(
        verbose_name=_("Default Deduction Per Miss"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    default_payment_period = models.IntegerField(
        verbose_name=_("Default Payment Period"),
        choices=choices.PAYMENT_PERIOD_CHOICES,
        default=3,
    )
    submission_grace_hours = models.PositiveIntegerField(
        verbose_name=_("Submission Grace Hours"),
        default=0,
    )
    requires_review = models.BooleanField(
        verbose_name=_("Requires Review"),
        default=True,
    )
    maintenance_mode = models.BooleanField(
        verbose_name=_("Maintenance Mode"),
        default=False,
    )

    class Meta:
        verbose_name = "Job Settings"
        verbose_name_plural = "Job Settings"


class Company(TimeStampedModel):
    name = models.CharField(
        verbose_name=_("Name"),
        max_length=150,
        unique=True,
    )
    logo = ImageField(
        verbose_name=_("Logo"),
        blank=True,
        null=True,
        upload_to=company_upload_to,
        validators=[encryption.validate_file_size],
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.COMPANY_STATUS_CHOICES,
        default=1,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.name

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class Job(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        verbose_name=_("Company"),
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=255,
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        null=True,
    )
    recurrence = models.IntegerField(
        verbose_name=_("Recurrence"),
        choices=choices.JOB_RECURRENCE_CHOICES,
        default=1,
    )
    payment_amount = models.DecimalField(
        verbose_name=_("Payment Amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    payment_period = models.IntegerField(
        verbose_name=_("Payment Period"),
        choices=choices.PAYMENT_PERIOD_CHOICES,
        default=3,
    )
    deduction_per_miss = models.DecimalField(
        verbose_name=_("Deduction Per Miss"),
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"), blank=True, null=True)
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.JOB_STATUS_CHOICES,
        default=1,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.title}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def is_live(self):
        today = timezone.localdate()
        if self.status != 2 or self.archived:
            return False
        if today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True


class JobRequirement(TimeStampedModel):
    job = models.ForeignKey(
        Job,
        verbose_name=_("Job"),
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    platform = models.IntegerField(
        verbose_name=_("Platform"),
        choices=choices.PLATFORM_CHOICES,
    )
    content_type = models.IntegerField(
        verbose_name=_("Content Type"),
        choices=choices.CONTENT_TYPE_CHOICES,
    )
    quantity = models.PositiveSmallIntegerField(
        verbose_name=_("Quantity"),
        default=1,
    )
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "platform", "content_type"],
                condition=models.Q(archived__isnull=True),
                name="unique_active_requirement_per_job",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.get_content_type_display()}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None
