import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.admins.models import Admin
from apps.jobs import choices
from apps.members.models import Member
from base.models import TimeStampedModel
from core import encryption


def company_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"company/{uuid4().hex}{ext}"


def proof_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"proof/{uuid4().hex}{ext}"


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
    telegram_link = models.URLField(
        verbose_name=_("Telegram Group Link"),
        max_length=500,
        blank=True,
        null=True,
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
    start_date = models.DateTimeField(verbose_name=_("Start Date"))
    end_date = models.DateTimeField(
        verbose_name=_("End Date"), blank=True, null=True,
    )
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
        now = timezone.now()
        if self.status != 2 or self.archived:
            return False
        if now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
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


class MemberJob(TimeStampedModel):
    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="member_jobs",
    )
    job = models.ForeignKey(
        Job,
        verbose_name=_("Job"),
        on_delete=models.CASCADE,
        related_name="member_jobs",
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.MEMBER_JOB_STATUS_CHOICES,
        default=1,
    )
    affiliate_link = models.URLField(
        verbose_name=_("Affiliate Link"),
        max_length=500,
        blank=True,
        null=True,
    )
    affiliate_link_status = models.IntegerField(
        verbose_name=_("Affiliate Link Status"),
        choices=choices.AFFILIATE_LINK_STATUS_CHOICES,
        default=1,
    )
    joined = models.DateField(blank=True, null=True)
    completed = models.DateField(blank=True, null=True)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "job"],
                condition=models.Q(archived__isnull=True),
                name="unique_active_member_job",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.member} - {self.job}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def is_active(self):
        return self.status == 2 and self.archived is None


class MemberTask(TimeStampedModel):
    member_job = models.ForeignKey(
        MemberJob,
        verbose_name=_("Member Job"),
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    requirement = models.ForeignKey(
        JobRequirement,
        verbose_name=_("Requirement"),
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    period_key = models.CharField(
        verbose_name=_("Period Key"),
        max_length=20,
    )
    period_start = models.DateField(verbose_name=_("Period Start"))
    period_end = models.DateField(verbose_name=_("Period End"))

    submitted_at = models.DateTimeField(blank=True, null=True)
    proof_link = models.URLField(max_length=500, blank=True, null=True)
    proof_file = models.FileField(
        blank=True,
        null=True,
        upload_to=proof_upload_to,
        validators=[encryption.validate_file_size],
    )
    note = models.TextField(blank=True, null=True)

    reviewed_at = models.DateTimeField(blank=True, null=True)
    is_approved = models.BooleanField(blank=True, null=True)
    reject_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        Admin,
        verbose_name=_("Reviewed By"),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_tasks",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member_job", "requirement", "period_key"],
                name="unique_task_per_period",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["period_key"]),
            models.Index(fields=["period_end"]),
            models.Index(fields=["submitted_at"]),
            models.Index(fields=["reviewed_at"]),
        ]

    def __str__(self):
        return f"{self.requirement} - {self.period_key}"

    @property
    def status(self):
        if self.reviewed_at:
            return 3 if self.is_approved else 4
        if self.submitted_at:
            return 2
        if self.period_end < timezone.localdate():
            return 5
        return 1

    @property
    def status_display(self):
        return dict(choices.MEMBER_TASK_STATUS_CHOICES)[self.status]

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    @property
    def is_fulfilled(self):
        # only an approved task avoids the deduction; rejected counts as missed
        return self.is_approved is True

    def submit(self, proof_link=None, proof_file=None, note=None):
        self.submitted_at = timezone.now()
        self.proof_link = proof_link
        if proof_file is not None:
            self.proof_file = proof_file
        self.note = note
        self.save()

    def review(self, admin, is_approved, reject_reason=None):
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin
        self.is_approved = is_approved
        self.reject_reason = reject_reason if not is_approved else None
        self.save()
