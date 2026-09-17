from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.members.models import Member
from base.models import TimeStampedModel
from core.encryption import decrypt_value, encrypt_value
from . import choices


class ThirdPartyConnection(TimeStampedModel):
    member = models.ForeignKey(
        Member,
        verbose_name=_("Member"),
        on_delete=models.CASCADE,
        related_name="third_party_connections",
    )
    provider = models.IntegerField(
        verbose_name=_("Provider"),
        choices=choices.PROVIDER_CHOICES,
    )
    account_id = models.CharField(max_length=100)
    account_label = models.CharField(max_length=150, blank=True, default="")
    access_token_encrypted = models.TextField()
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.CharField(max_length=500, blank=True, default="")
    connected_at = models.DateTimeField(default=timezone.now)
    archived = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "provider"],
                condition=models.Q(archived__isnull=True),
                name="unique_active_third_party_connection_per_member",
            ),
        ]
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["provider"]),
        ]

    def set_access_token(self, raw_token: str):
        self.access_token_encrypted = encrypt_value(raw_token)

    def get_access_token(self) -> str:
        return decrypt_value(self.access_token_encrypted)

    @property
    def is_expired(self):
        return bool(self.token_expires_at and self.token_expires_at <= timezone.now())

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None
