import datetime

from django.utils import timezone
from rest_framework import serializers

from apps.jobs import choices
from core import encryption


def _normalize_end_date(end_date):
    """A midnight `end_date` (date picker sending start-of-day, no time
    component) would otherwise close the job before it ever opens. Treat it
    as "through the end of that day" instead.
    """
    if end_date is None:
        return end_date
    local = timezone.localtime(end_date)
    if local.time() == datetime.time.min:
        local = local.replace(hour=23, minute=59, second=59, microsecond=999999)
        return local.astimezone(datetime.timezone.utc)
    return end_date


class OrgSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    status = serializers.ChoiceField(
        choices=choices.COMPANY_STATUS_CHOICES, default=1,
    )
    telegram_link = serializers.URLField(
        required=False, allow_null=True, allow_blank=True,
    )
    logo = serializers.ImageField(required=False, allow_null=True)


class EditOrgSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    status = serializers.ChoiceField(
        choices=choices.COMPANY_STATUS_CHOICES, required=False,
    )
    telegram_link = serializers.URLField(
        required=False, allow_null=True, allow_blank=True,
    )
    logo = serializers.ImageField(required=False, allow_null=True)


class JobRequirementSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=choices.PLATFORM_CHOICES, required=True)
    content_type = serializers.ChoiceField(
        choices=choices.CONTENT_TYPE_CHOICES, required=True,
    )
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)


class EditJobRequirementSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(
        choices=choices.PLATFORM_CHOICES, required=False,
    )
    content_type = serializers.ChoiceField(
        choices=choices.CONTENT_TYPE_CHOICES, required=False,
    )
    quantity = serializers.IntegerField(required=False, min_value=1)


class JobSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
    script = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=5000,
    )
    recurrence = serializers.ChoiceField(
        choices=choices.JOB_RECURRENCE_CHOICES, default=1,
    )
    payment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=True,
    )
    payment_period = serializers.ChoiceField(
        choices=choices.PAYMENT_PERIOD_CHOICES, default=3,
    )
    deduction_per_miss = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=True,
    )
    start_date = serializers.DateTimeField(required=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=choices.JOB_STATUS_CHOICES, default=1)
    requirements = JobRequirementSerializer(many=True, required=False)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if end_date is not None:
            end_date = attrs["end_date"] = _normalize_end_date(end_date)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })
        return attrs


class EditJobSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
    script = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=5000,
    )
    recurrence = serializers.ChoiceField(
        choices=choices.JOB_RECURRENCE_CHOICES, required=False,
    )
    payment_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False,
    )
    payment_period = serializers.ChoiceField(
        choices=choices.PAYMENT_PERIOD_CHOICES, required=False,
    )
    deduction_per_miss = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False,
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=choices.JOB_STATUS_CHOICES, required=False,
    )

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if end_date is not None:
            end_date = attrs["end_date"] = _normalize_end_date(end_date)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })
        return attrs


class ApproveMemberJobSerializer(serializers.Serializer):
    affiliate_link = serializers.URLField(
        required=False, allow_null=True, allow_blank=True,
    )


class EditMemberJobSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=choices.MEMBER_JOB_STATUS_CHOICES, required=False,
    )
    affiliate_link = serializers.URLField(
        required=False, allow_null=True, allow_blank=True,
    )
    affiliate_link_status = serializers.ChoiceField(
        choices=choices.AFFILIATE_LINK_STATUS_CHOICES, required=False,
    )


class SubmitTaskSerializer(serializers.Serializer):
    proof_link = serializers.URLField(
        required=False, allow_null=True, allow_blank=True,
    )
    proof_file = serializers.FileField(required=False, allow_null=True)
    note = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )

    def validate(self, attrs):
        if not attrs.get("proof_link") and not attrs.get("proof_file"):
            raise serializers.ValidationError(
                "Either a proof link or a proof file is required."
            )
        return attrs


class RejectTaskSerializer(serializers.Serializer):
    reject_reason = serializers.CharField(required=True)


class JobSettingsSerializer(serializers.Serializer):
    default_deduction_per_miss = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False,
    )
    default_payment_period = serializers.ChoiceField(
        choices=choices.PAYMENT_PERIOD_CHOICES, required=False,
    )
    submission_grace_hours = serializers.IntegerField(required=False, min_value=0)
    requires_review = serializers.BooleanField(required=False)
    maintenance_mode = serializers.BooleanField(required=False)


class TaskContentSerializer(serializers.Serializer):
    """The finished reel / photo files for one task."""

    files = serializers.ListField(
        child=serializers.FileField(
            validators=[encryption.validate_content_file_size],
        ),
        allow_empty=False,
        max_length=20,
    )


class TaskResultSerializer(serializers.Serializer):
    """How the post performed, via a metrics screenshot."""

    metrics_screenshot = serializers.FileField(required=True)
