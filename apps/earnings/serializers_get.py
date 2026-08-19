from rest_framework import serializers

from apps.earnings import models


class PayoutSerializer(serializers.ModelSerializer):
    member = serializers.CharField(source="member.full_name")
    member_uuid = serializers.UUIDField(source="member.uuid")
    status = serializers.IntegerField()
    status_display = serializers.CharField()

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
            "status_display",
            "paid_at",
            "created",
        ]


class EarningsJobSerializer(serializers.Serializer):
    member_job_uuid = serializers.UUIDField()
    company = serializers.CharField()
    job_title = serializers.CharField()
    payment_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_period = serializers.CharField()
    cycles = serializers.IntegerField()
    base_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class EarningsSerializer(serializers.Serializer):
    period_key = serializers.CharField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()
    base_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    missed_count = serializers.IntegerField()
    deduction = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    jobs = EarningsJobSerializer(many=True)


class MissedDaySerializer(serializers.Serializer):
    member_job_uuid = serializers.UUIDField()
    company = serializers.CharField()
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
