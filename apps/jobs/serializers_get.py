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
            "telegram_link",
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


class MemberJobSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.full_name")
    member_uuid = serializers.UUIDField(source="member.uuid")
    username = serializers.CharField(source="member.user.username")
    company = serializers.CharField(source="job.company.name")
    company_logo = serializers.ImageField(source="job.company.logo")
    job_uuid = serializers.UUIDField(source="job.uuid")
    job_title = serializers.CharField(source="job.title")
    payment_amount = serializers.DecimalField(
        source="job.payment_amount", max_digits=12, decimal_places=2,
    )
    payment_period = serializers.CharField(source="job.get_payment_period_display")
    recurrence = serializers.CharField(source="job.get_recurrence_display")
    status = serializers.CharField(source="get_status_display")
    affiliate_link_status = serializers.CharField(
        source="get_affiliate_link_status_display",
    )

    class Meta:
        model = models.MemberJob
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "username",
            "company",
            "company_logo",
            "job_uuid",
            "job_title",
            "payment_amount",
            "payment_period",
            "recurrence",
            "status",
            "affiliate_link",
            "affiliate_link_status",
            "joined",
            "completed",
            "created",
        ]


class MemberTaskSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member_job.member.full_name")
    member_uuid = serializers.UUIDField(source="member_job.member.uuid")
    company = serializers.CharField(source="member_job.job.company.name")
    job_title = serializers.CharField(source="member_job.job.title")
    member_job_uuid = serializers.UUIDField(source="member_job.uuid")
    platform = serializers.CharField(source="requirement.get_platform_display")
    content_type = serializers.CharField(source="requirement.get_content_type_display")
    quantity = serializers.IntegerField(source="requirement.quantity")
    status = serializers.IntegerField()
    status_display = serializers.CharField()

    class Meta:
        model = models.MemberTask
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "company",
            "job_title",
            "member_job_uuid",
            "platform",
            "content_type",
            "quantity",
            "period_key",
            "period_start",
            "period_end",
            "status",
            "status_display",
            "proof_link",
            "proof_file",
            "note",
            "submitted_at",
            "reviewed_at",
            "is_approved",
            "reject_reason",
        ]


class AvailableJobSerializer(JobSerializer):
    is_applied = serializers.SerializerMethodField()

    def get_is_applied(self, obj):
        applied = self.context.get("applied_job_ids") or set()
        return obj.id in applied

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ["is_applied"]


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
