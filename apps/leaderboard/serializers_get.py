from rest_framework import serializers


class RankingRowSerializer(serializers.Serializer):
    ranking = serializers.IntegerField()
    member_uuid = serializers.UUIDField()
    full_name = serializers.CharField(allow_null=True)
    username = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class MemberRankingSerializer(serializers.Serializer):
    member_uuid = serializers.UUIDField()
    full_name = serializers.CharField(allow_null=True)
    username = serializers.CharField()
    ranking = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    next_rank = serializers.IntegerField(allow_null=True)
    next_rank_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True,
    )
    amount_needed = serializers.DecimalField(max_digits=12, decimal_places=2)


class RankingKpiSerializer(serializers.Serializer):
    member_count = serializers.IntegerField()
    earning_member_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    average_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    top_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
