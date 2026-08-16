import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from sorl.thumbnail import ImageField

from apps.members import choices
from base.models import TimeStampedModel, UserModel
from core import encryption


def member_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"member/{uuid4().hex}{ext}"


class Member(TimeStampedModel):
    user = models.OneToOneField(
        UserModel,
        verbose_name=_("User"),
        on_delete=models.CASCADE,
        related_name="member",
    )
    display_name = models.CharField(
        verbose_name=_("Display Name"),
        max_length=150,
        blank=True,
        null=True,
    )
    profile_picture = ImageField(
        verbose_name=_("Profile Picture"),
        blank=True,
        null=True,
        upload_to=member_upload_to,
        validators=[encryption.validate_file_size],
    )
    status = models.IntegerField(
        verbose_name=_("Status"),
        choices=choices.MEMBER_STATUS_CHOICES,
        default=1,
    )
    affiliate_link = models.URLField(
        verbose_name=_("Affiliate Link"),
        max_length=500,
        blank=True,
        null=True,
    )
    telegram_link = models.URLField(
        verbose_name=_("Telegram Group Link"),
        max_length=500,
        blank=True,
        null=True,
    )
    joined = models.DateField(blank=True, null=True)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.display_name or self.user.username

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class BankDetail(TimeStampedModel):
    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="bank_details",
    )
    bank = models.IntegerField(
        verbose_name=_("Bank"),
        choices=choices.BANK_CHOICES,
    )
    account_holder_name = models.CharField(
        verbose_name=_("Account Holder Name"),
        max_length=150,
    )
    account_number = models.CharField(
        verbose_name=_("Account Number"),
        max_length=64,
    )
    is_primary = models.BooleanField(default=True)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["is_primary"]),
        ]

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class PlatformAccount(TimeStampedModel):
    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="platform_accounts",
    )
    platform = models.IntegerField(
        verbose_name=_("Platform"),
        choices=choices.PLATFORM_CHOICES,
    )
    handle = models.CharField(
        verbose_name=_("Handle"),
        max_length=150,
    )
    profile_url = models.URLField(
        verbose_name=_("Profile Url"),
        max_length=500,
        blank=True,
        null=True,
    )
    is_verified = models.BooleanField(default=False)
    last_synced = models.DateTimeField(blank=True, null=True)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "platform"],
                condition=models.Q(archived__isnull=True),
                name="unique_active_platform_per_member",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["platform"]),
        ]

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None


class LoginAudit(TimeStampedModel):
    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="login_audits",
    )
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    device = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
        ]
