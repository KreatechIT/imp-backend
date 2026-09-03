from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.notifications import choices
from base.models import TimeStampedModel


class Notification(TimeStampedModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Recipient"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    role = models.IntegerField(
        verbose_name=_("Recipient Role"),
        choices=choices.RECIPIENT_ROLE_CHOICES,
    )
    notification_type = models.IntegerField(
        verbose_name=_("Type"),
        choices=choices.NOTIFICATION_TYPE_CHOICES,
    )
    title = models.CharField(
        verbose_name=_("Title"),
        max_length=150,
    )
    message = models.CharField(
        verbose_name=_("Message"),
        max_length=500,
        blank=True,
        null=True,
    )

    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["recipient", "read_at"]),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save()

    @property
    def is_read(self):
        return self.read_at is not None
