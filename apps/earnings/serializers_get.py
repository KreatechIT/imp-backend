from rest_framework import serializers

from apps.earnings import models


class PayoutSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.full_name")
    member_uuid = serializers.UUIDField(source="member.uuid")
    status = serializers.IntegerField()

    class Meta:
        model = models.Payout
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "period_key",
            "amount",
            "note",
            "status",
            "paid_at",
            "created",
        ]


class EarningsJobSerializer(serializers.Serializer):
    member_job_uuid = serializers.UUIDField()
    org = serializers.CharField()
    job_title = serializers.CharField()
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_period = serializers.IntegerField()
    cycles = serializers.IntegerField()
    base_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    missed_count = serializers.IntegerField()
    posted_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class EarningsSerializer(serializers.Serializer):
    period_key = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    base_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    missed_count = serializers.IntegerField()
    posted_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    jobs = EarningsJobSerializer(many=True)


class MissedDaySerializer(serializers.Serializer):
    member_job_uuid = serializers.UUIDField()
    org = serializers.CharField()
    job_title = serializers.CharField()
    period_key = serializers.CharField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)


class MissedSerializer(serializers.Serializer):
    period_key = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    days = MissedDaySerializer(many=True)


class StatisticsRowSerializer(serializers.Serializer):
    member_uuid = serializers.UUIDField()
    full_name = serializers.CharField()
    username = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.CharField()
    status = serializers.IntegerField()
    job_count = serializers.IntegerField()
    base_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    posted_count = serializers.IntegerField()
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class StatisticsSummarySerializer(serializers.Serializer):
    period_key = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    member_count = serializers.IntegerField()
    earning_member_count = serializers.IntegerField()
    missed_member_count = serializers.IntegerField()
    base_pay = serializers.DecimalField(max_digits=14, decimal_places=2)
    posted_count = serializers.IntegerField()
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class EarningsKpiSerializer(serializers.Serializer):
    member_count = serializers.IntegerField()
    earning_member_count = serializers.IntegerField()
    missed_member_count = serializers.IntegerField()
    base_pay = serializers.DecimalField(max_digits=14, decimal_places=2)
    posted_count = serializers.IntegerField()
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)


class JobPayoutSerializer(serializers.ModelSerializer):
    member = serializers.SerializerMethodField()
    member_uuid = serializers.UUIDField(source="member_job.member.uuid")
    member_job_uuid = serializers.UUIDField(source="member_job.uuid")
    org = serializers.CharField(source="member_job.job.company.name")
    job_title = serializers.CharField(source="member_job.job.title")
    job_end_date = serializers.DateTimeField(source="member_job.job.end_date")
    reviewed_by = serializers.SerializerMethodField()

    def get_member(self, obj):
        member = obj.member_job.member
        return member.full_name or member.user.username

    def get_reviewed_by(self, obj):
        if obj.reviewed_by is None:
            return None
        return obj.reviewed_by.user.username

    class Meta:
        model = models.JobPayout
        fields = [
            "uuid",
            "member",
            "member_uuid",
            "member_job_uuid",
            "org",
            "job_title",
            "job_end_date",
            "amount",
            "status",
            "reject_reason",
            "reviewed_by",
            "reviewed_at",
            "paid_at",
            "created",
        ]


class PayoutJobSerializer(serializers.Serializer):
    member_job_uuid = serializers.UUIDField()
    org = serializers.CharField()
    job_title = serializers.CharField()
    end_date = serializers.DateTimeField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    can_request = serializers.BooleanField()
    blocked_reason = serializers.CharField(allow_null=True)
    payout_uuid = serializers.UUIDField(allow_null=True)
    payout_status = serializers.IntegerField(allow_null=True)
    reject_reason = serializers.CharField(allow_null=True)
