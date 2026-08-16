from rest_framework import serializers

from apps.jobs import models


class CompanySerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="get_status_display")
    total_jobs = serializers.SerializerMethodField()

    def get_total_jobs(self, obj):
        return obj.jobs.filter(archived=None).count()

    class Meta:
        model = models.Company
        fields = [
            "uuid",
            "name",
            "logo",
            "status",
            "total_jobs",
            "created",
        ]


class JobRequirementSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="get_platform_display")
    content_type = serializers.CharField(source="get_content_type_display")

    class Meta:
        model = models.JobRequirement
        fields = [
            "uuid",
            "platform",
            "content_type",
            "quantity",
        ]


class JobSerializer(serializers.ModelSerializer):
    company = serializers.CharField(source="company.name")
    company_uuid = serializers.UUIDField(source="company.uuid")
    company_logo = serializers.ImageField(source="company.logo")
    recurrence = serializers.CharField(source="get_recurrence_display")
    payment_period = serializers.CharField(source="get_payment_period_display")
    status = serializers.CharField(source="get_status_display")
    is_live = serializers.BooleanField()
    requirements = serializers.SerializerMethodField()

    def get_requirements(self, obj):
        queryset = obj.requirements.filter(archived=None).order_by("content_type")
        return JobRequirementSerializer(queryset, many=True).data

    class Meta:
        model = models.Job
        fields = [
            "uuid",
            "company",
            "company_uuid",
            "company_logo",
            "title",
            "description",
            "recurrence",
            "payment_amount",
            "payment_period",
            "deduction_per_miss",
            "start_date",
            "end_date",
            "status",
            "is_live",
            "requirements",
            "created",
        ]


class JobSettingsSerializer(serializers.ModelSerializer):
    default_payment_period = serializers.CharField(
        source="get_default_payment_period_display",
    )

    class Meta:
        model = models.JobSettings
        fields = [
            "uuid",
            "default_deduction_per_miss",
            "default_payment_period",
            "submission_grace_hours",
            "requires_review",
            "maintenance_mode",
        ]
