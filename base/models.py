import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        return self.get(username=username)

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, password, **extra_fields)


class UUIDModel(models.Model):
    """Integer primary key plus a public uuid, which is what viewsets expose."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        related_name="%(app_label)s_%(class)s_created_user",
        on_delete=models.SET_NULL,
        editable=False,
    )
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

        indexes = [
            models.Index(fields=["created"]),
        ]

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()


class UserModel(AbstractBaseUser):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    username = models.CharField(
        _("Username"),
        max_length=128,
        unique=True,
    )
    password = models.CharField(
        _("Password"),
        max_length=128,
        blank=True,
        null=True,
    )

    archived = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [
            models.Index(fields=["username"]),
        ]

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()

    def archive(self):
        self.archived = timezone.now()
        self.save()

    @property
    def is_archived(self):
        return self.archived is not None

    @property
    def is_admin(self):
        return getattr(self, "admin", None)

    @property
    def is_member(self):
        return getattr(self, "member", None)
