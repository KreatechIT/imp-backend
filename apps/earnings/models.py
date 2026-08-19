from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.earnings import choices
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
