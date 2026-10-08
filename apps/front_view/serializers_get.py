from rest_framework import serializers

from apps.front_view import models


class BannerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Banner
        fields = [
            "uuid",
            "name",
            "image",
            "link",
            "location",
            "active_from",
            "active_until",
            "ordering",
            "is_live",
            "created",
        ]


class DummyInfluencerSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.DummyInfluencer
        fields = [
            "uuid",
            "full_name",
            "phone_number",
            "deposit_amount",
            "reg_count",
            "cvs_count",
            "created",
        ]


class GuideSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Guide
        fields = [
            "uuid",
            "location",
            "title",
            "content",
            "ordering",
            "modified",
        ]


class TermsAndConditionsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.TermsAndConditions
        fields = [
            "uuid",
            "category",
            "content",
            "modified",
        ]


class SingleTermsAndConditionsSerializer(serializers.ModelSerializer):
    """Flat shape for the public/<category>/ lookup — content only."""

    class Meta:
        model = models.TermsAndConditions
        fields = ["content"]


class InfluencerSnapshotSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.InfluencerSnapshot
        fields = [
            "rank",
            "member_uuid",
            "full_name",
            "phone_number",
            "reg_count",
            "cvs_count",
            "deposit_amount",
        ]


class InfluencerSyncRunSerializer(serializers.ModelSerializer):
    slot_display = serializers.CharField(source="get_slot_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = models.InfluencerSyncRun
        fields = [
            "uuid",
            "slot",
            "slot_display",
            "status",
            "status_display",
            "attempt",
            "row_count",
            "error",
            "created",
        ]


class InfluencerSyncRunDetailSerializer(InfluencerSyncRunSerializer):
    rows = InfluencerSnapshotSerializer(many=True, read_only=True)

    class Meta(InfluencerSyncRunSerializer.Meta):
        fields = InfluencerSyncRunSerializer.Meta.fields + ["not_found", "rows"]
