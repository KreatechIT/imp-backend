from rest_framework import serializers

from apps.jobs import models


class OrgSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = models.JobRequirement
        fields = [
            "uuid",
            "platform",
            "content_type",
            "quantity",
        ]


class JobSerializer(serializers.ModelSerializer):
    org = serializers.CharField(source="company.name")
    org_uuid = serializers.UUIDField(source="company.uuid")
    org_logo = serializers.ImageField(source="company.logo")
    is_live = serializers.BooleanField()
    requirements = serializers.SerializerMethodField()

    def get_requirements(self, obj):
        queryset = obj.requirements.filter(archived=None).order_by("content_type")
        return JobRequirementSerializer(queryset, many=True).data

    class Meta:
        model = models.Job
        fields = [
            "uuid",
            "org",
            "org_uuid",
            "org_logo",
            "title",
            "description",
            "script",
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
    member = serializers.CharField(source="member.display_name")
    member_uuid = serializers.UUIDField(source="member.uuid")
    username = serializers.CharField(source="member.user.username")
    org = serializers.CharField(source="job.company.name")
    org_uuid = serializers.UUIDField(source="job.company.uuid")
    org_logo = serializers.ImageField(source="job.company.logo")
    job_uuid = serializers.UUIDField(source="job.uuid")
    job_title = serializers.CharField(source="job.title")
    payment_amount = serializers.DecimalField(
        source="job.payment_amount", max_digits=12, decimal_places=2,
    )
    payment_period = serializers.IntegerField(source="job.payment_period")
    recurrence = serializers.IntegerField(source="job.recurrence")
    has_frames = serializers.SerializerMethodField()

    def get_has_frames(self, obj):
        return obj.job.frames.filter(status=1, archived=None).exists()

    class Meta:
        model = models.MemberJob
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "username",
            "org",
            "org_uuid",
            "org_logo",
            "job_uuid",
            "job_title",
            "payment_amount",
            "payment_period",
            "recurrence",
            "status",
            "affiliate_link",
            "affiliate_link_status",
            "has_frames",
            "joined",
            "completed",
            "created",
        ]


class PendingResultsJobSerializer(serializers.ModelSerializer):
    org = serializers.CharField(source="job.company.name")
    job_title = serializers.CharField(source="job.title")
    pending_result_count = serializers.IntegerField()

    class Meta:
        model = models.MemberJob
        fields = ["uuid", "org", "job_title", "pending_result_count"]


class PendingResultsTaskSerializer(serializers.ModelSerializer):
    platform = serializers.IntegerField(source="requirement.platform")
    content_type = serializers.IntegerField(source="requirement.content_type")

    class Meta:
        model = models.MemberTask
        fields = ["uuid", "platform", "content_type"]


class TaskFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TaskFile
        fields = [
            "uuid",
            "file",
            "media_type",
            "original_name",
            "size",
            "created",
        ]


class MemberTaskSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member_job.member.display_name")
    member_uuid = serializers.UUIDField(source="member_job.member.uuid")
    org = serializers.CharField(source="member_job.job.company.name")
    org_uuid = serializers.UUIDField(source="member_job.job.company.uuid")
    job_title = serializers.CharField(source="member_job.job.title")
    job_uuid = serializers.UUIDField(source="member_job.job.uuid")
    job_description = serializers.CharField(
        source="member_job.job.description", allow_null=True, allow_blank=True,
    )
    job_script = serializers.CharField(
        source="member_job.job.script", allow_null=True, allow_blank=True,
    )
    member_job_uuid = serializers.UUIDField(source="member_job.uuid")
    platform = serializers.IntegerField(source="requirement.platform")
    content_type = serializers.IntegerField(source="requirement.content_type")
    quantity = serializers.IntegerField(source="requirement.quantity")
    status = serializers.IntegerField()
    files = serializers.SerializerMethodField()
    proof_required = serializers.SerializerMethodField()
    is_auto_approved = serializers.BooleanField(read_only=True)

    def get_files(self, obj):
        queryset = obj.files.filter(archived=None).order_by("created")
        return TaskFileSerializer(
            queryset, many=True, context=self.context,
        ).data

    def get_proof_required(self, obj):
        # one settings lookup per serializer, not per row
        if "proof_required" not in self.context:
            settings_row = models.JobSettings.objects.first()
            self.context["proof_required"] = (
                settings_row.requires_review if settings_row else True
            )
        return self.context["proof_required"]

    class Meta:
        model = models.MemberTask
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "org",
            "org_uuid",
            "job_title",
            "job_uuid",
            "job_description",
            "job_script",
            "member_job_uuid",
            "platform",
            "content_type",
            "quantity",
            "period_key",
            "period_start",
            "period_end",
            "status",
            "proof_link",
            "proof_file",
            "note",
            "submitted_at",
            "reviewed_at",
            "is_approved",
            "reject_reason",
            "files",
            "metrics_screenshot",
            "metrics_submitted_at",
            "metrics_views",
            "result_status",
            "result_reject_reason",
            "has_result",
            "proof_required",
            "is_auto_approved",
        ]


class MissedRequirementSerializer(serializers.Serializer):
    platform = serializers.IntegerField()
    content_type = serializers.IntegerField()
    quantity = serializers.IntegerField()


class MissedSubmissionSerializer(serializers.Serializer):
    member = serializers.CharField()
    member_uuid = serializers.UUIDField()
    username = serializers.CharField()
    phone_number = serializers.CharField(allow_null=True, allow_blank=True)
    member_job_uuid = serializers.UUIDField()
    org = serializers.CharField()
    job_title = serializers.CharField()
    requirements = MissedRequirementSerializer(many=True)
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    period_key = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()


class JobMemberSerializer(MemberJobSerializer):
    result_views = serializers.SerializerMethodField()
    results_to_review = serializers.SerializerMethodField()

    def get_result_views(self, obj):
        return getattr(obj, "result_views", 0) or 0

    def get_results_to_review(self, obj):
        return getattr(obj, "results_to_review", 0) or 0

    class Meta(MemberJobSerializer.Meta):
        fields = MemberJobSerializer.Meta.fields + [
            "result_views",
            "results_to_review",
        ]


class AvailableJobSerializer(JobSerializer):
    is_applied = serializers.SerializerMethodField()

    def get_is_applied(self, obj):
        applied = self.context.get("applied_job_ids") or set()
        return obj.id in applied

    class Meta(JobSerializer.Meta):
        fields = JobSerializer.Meta.fields + ["is_applied"]


class JobSettingsSerializer(serializers.ModelSerializer):
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
