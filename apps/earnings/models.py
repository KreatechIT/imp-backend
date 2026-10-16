from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.crmadmin.models import Admin
from apps.earnings import choices
from apps.jobs.models import MemberJob
from apps.members.models import Member
from base.models import TimeStampedModel


class Payout(TimeStampedModel):
    """One month's settled payment, kept so payment history survives edits."""

    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="payouts",
    )
    period_key = models.CharField(
        verbose_name=_("Period Key"),
        max_length=20,
    )
    amount = models.DecimalField(
        verbose_name=_("Amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    note = models.TextField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "period_key"],
                condition=models.Q(archived__isnull=True),
                name="unique_active_payout_per_period",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["period_key"]),
            models.Index(fields=["paid_at"]),
        ]

    def __str__(self):
        return f"{self.member} - {self.period_key}"

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def status(self):
        return 2 if self.paid_at else 1

    @property
    def status_display(self):
        return dict(choices.PAYOUT_STATUS_CHOICES)[self.status]

    def mark_paid(self):
        self.paid_at = timezone.now()
        self.save()


class JobPayout(TimeStampedModel):
    member_job = models.ForeignKey(
        MemberJob,
        verbose_name=_("Member Job"),
        on_delete=models.CASCADE,
        related_name="job_payouts",
    )
    amount = models.DecimalField(
        verbose_name=_("Amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.JOB_PAYOUT_STATUS_CHOICES,
        default=1,
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        Admin,
        verbose_name=_("Reviewed By"),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_job_payouts",
    )
    reject_reason = models.TextField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member_job"],
                condition=models.Q(status__in=[1, 2, 4]),
                name="unique_live_payout_per_member_job",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.member_job} - {self.status_display}"

    @property
    def status_display(self):
        return dict(choices.JOB_PAYOUT_STATUS_CHOICES)[self.status]

    def approve(self, admin):
        self.status = 2
        self.reviewed_by = admin
        self.reviewed_at = timezone.now()
        self.reject_reason = None
        self.save()

    def reject(self, admin, reason):
        self.status = 3
        self.reviewed_by = admin
        self.reviewed_at = timezone.now()
        self.reject_reason = reason
        self.save()

    def mark_paid(self):
        self.status = 4
        self.paid_at = timezone.now()
        self.save()
