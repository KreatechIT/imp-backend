import re

from rest_framework import serializers

MONTH_KEY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class MonthQuerySerializer(serializers.Serializer):
    month = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    def validate_month(self, value):
        if value and not MONTH_KEY.match(value):
            raise serializers.ValidationError("Month must look like YYYY-MM.")
        return value or None


class PayoutSerializer(serializers.Serializer):
    member_uuid = serializers.UUIDField(required=True)
    period_key = serializers.CharField(required=True)
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=True,
    )
    note = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )

    def validate_period_key(self, value):
        if not MONTH_KEY.match(value):
            raise serializers.ValidationError("Period must look like YYYY-MM.")
        return value


class EditPayoutSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False,
    )
    note = serializers.CharField(
        required=False, allow_null=True, allow_blank=True,
    )
